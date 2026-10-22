import io
import json
import threading

import httpx
from PIL import Image
import pytest

from cutris.settings import SettingsStore, validate_settings
from test_server import api, wait


def fixture_png():
    image=Image.new('RGBA',(50,40))
    image.paste((100,150,200,255),(10,8,40,32))
    stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()


def test_settings_persist_and_reject_bad_values(tmp_path):
    store=SettingsStore(tmp_path/'settings.json')
    assert store.get()['auto_crop'] is True
    values=store.update({'output_folder':str(tmp_path/'exports'),'quality':'fast','wheel_zoom':False})
    assert SettingsStore(store.path).get()==values
    for values in ({'unknown':True},{'quality':{}},{'mode':'unknown'},{'auto_crop':1},{'output_folder':'relative/folder'}):
        with pytest.raises(ValueError):store.update(values)
    assert store.get()['quality']=='fast'
    assert not store.path.with_suffix('.tmp').exists()


def test_export_folder_png_zip_crop_and_collision_safety(api,tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'SETTINGS',SettingsStore(tmp_path/'preferences.json'))
    folder=tmp_path/'exports'
    assert api.put('/api/settings',json={'output_folder':str(folder),'quality':'fast'}).status_code==200
    assert api.get('/api/config').json()['preferences']['quality']=='fast'
    job=wait(api,api.post('/api/jobs',files=[('files',('sample.png',fixture_png(),'image/png'))]).json()['id'])
    item=job['items'][0]
    result=api.post('/api/exports/'+job['id'],json={'item_id':item['id']})
    assert result.status_code==200
    first=folder/result.json()['name'];before=first.read_bytes()
    assert Image.open(first).size==(30,24)
    second=api.post('/api/exports/'+job['id'],json={'item_id':item['id']}).json()
    assert second['name']!=first.name and first.read_bytes()==before
    assert api.put('/api/settings',json={'auto_crop':False}).status_code==200
    third=api.post('/api/exports/'+job['id'],json={'item_id':item['id']}).json()
    assert Image.open(folder/third['name']).size==(50,40)
    archive=api.post('/api/exports/'+job['id'],json={})
    assert archive.status_code==200 and (folder/archive.json()['name']).suffix=='.zip'
    assert api.post('/api/exports/'+job['id'],json={'item_id':'../source'}).status_code==422


def test_api_key_is_never_anonymous_and_editor_handoff_loads_saved_projects(api,tmp_path,monkeypatch):
    import server
    from types import SimpleNamespace
    monkeypatch.setattr(server,'SETTINGS',SettingsStore(tmp_path/'preferences.json'))
    monkeypatch.setattr(server,'EDITOR_REQUESTS',[])
    monkeypatch.setattr(server,'INTEGRATION_CONTROLLER',SimpleNamespace(status=lambda:{'enabled':True},token='private-fixture-key'))
    assert api.get('/api/integration/key',headers={'X-Cutout-Token':'wrong'}).status_code==403
    assert api.get('/api/integration/key').json()['key']=='private-fixture-key'
    project_id='a'*32;directory=server.DATA/project_id;directory.mkdir()
    (directory/'manifest.json').write_text(json.dumps({'id':project_id,'status':'complete','items':[]}))
    assert server.request_editor(project_id)['ok']
    assert api.post('/api/integration/next').json()['project_id']==project_id
    assert api.post('/api/integration/next').json()['project_id'] is None


def test_desktop_api_shares_processor_authenticates_and_opens_editor(tmp_path,monkeypatch):
    from cutris import runtime,projects
    monkeypatch.setattr(runtime,'DATA_DIR',tmp_path/'data')
    monkeypatch.setattr(projects,'DATA_DIR',tmp_path/'data')
    monkeypatch.setattr(runtime,'user_state',lambda:tmp_path/'global')
    class FakeRemover:
        def process(self,image,*args):return image,['Fixture']
    remover=FakeRemover();lock=threading.Lock();opened=[]
    service=runtime.IntegrationRuntime(remover=remover,lock=lock,open_editor=lambda project_id:opened.append(project_id) or {'ok':True},state_dir=tmp_path/'integration')
    try:
        service.start()
        assert service.processor.remover is remover and service.processor.lock is lock
        descriptor=json.loads((tmp_path/'global'/'service.json').read_text())
        assert descriptor['source']=='desktop' and 'token' not in descriptor
        with httpx.Client(base_url=service.origin,timeout=5) as client:
            assert client.get('/v1/health').status_code==401
            headers={'Authorization':'Bearer '+service.token}
            assert client.get('/v1/health',headers=headers).json()['editor_available'] is True
            result=client.post('/v1/remove',headers=headers,files={'file':('fixture.png',fixture_png(),'image/png')},data={'editable':'true'})
            assert result.status_code==200
            project_id=result.headers['X-Cutris-Project']
            assert client.get('/v1/projects/'+project_id,headers=headers).json()['revision']==0
            assert client.get('/v1/projects/../invalid',headers=headers).status_code==404
            response=client.post('/v1/editor/open',headers=headers,json={'project_id':project_id})
            assert response.status_code==200 and opened==[project_id]
            assert client.post('/v1/editor/open',headers=headers,json={'project_id':'../data'}).status_code==422
    finally:service.stop()
    assert not (tmp_path/'integration'/'service.json').exists()
    assert not (tmp_path/'global'/'service.json').exists()
