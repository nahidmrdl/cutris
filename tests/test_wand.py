import io

import numpy as np
from PIL import Image

from engine import apply_strokes
from test_server import api, picture, wait


def test_wand_replays_exact_spans_and_preserves_original():
    original=Image.new('RGBA',(80,60),'white')
    automatic=original.copy()
    action={'mode':'wand','spans':[[10,20,30],[11,20,30]]}
    cutout=np.array(apply_strokes(original,automatic,[action]))
    assert np.all(cutout[10:12,20:30,3]==0)
    assert cutout[10,19,3]==255 and cutout[12,20,3]==255
    assert original.getpixel((20,10))[3]==255
    restored=apply_strokes(original,automatic,[action,{'mode':'restore','size':5,'points':[[25,10]]}])
    assert restored.getpixel((25,10))[3]==255
    assert np.array_equal(np.array(apply_strokes(original,automatic,[])),np.array(automatic))


def test_wand_save_reload_and_validation(api):
    job=wait(api,api.post('/api/jobs',files=[('files',('test.png',picture(),'image/png'))]).json()['id'])
    item=job['items'][0]
    path=f'/api/jobs/{job["id"]}/items/{item["id"]}'
    for action in [
        {'mode':'wand','spans':[[0,-1,10]]},
        {'mode':'wand','spans':[[40,1,10]]},
        {'mode':'wand','spans':[[2,10,9]]},
        {'mode':'wand','spans':[[2,1,51]]},
        {'mode':'wand','spans':[]},
        {'mode':'erase','points':[]},
    ]:
        assert api.put(path+'/edits',json={'revision':0,'strokes':[action]}).status_code==400
    action={'mode':'wand','spans':[[10,20,30],[11,20,30]]}
    assert api.put(path+'/edits',json={'revision':0,'strokes':[action]}).status_code==200
    saved=api.get('/api/jobs/'+job['id']).json()['items'][0]['strokes'][0]
    assert saved['mode']=='wand' and saved['spans']==action['spans']
    result=Image.open(io.BytesIO(api.get(path+'/result').content))
    assert result.getpixel((25,10))[3]==0 and result.getpixel((19,10))[3]==255
    assert api.put(path+'/edits',json={'revision':1,'strokes':[]}).status_code==200
