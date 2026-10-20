import io
import json
import zipfile

import pytest
from PIL import Image

from test_server import api, picture, wait
from test_transform_api import png, transparent_subject


def create_batch(api):
    response = api.post('/api/jobs', files=[
        ('files', ('subject.png', transparent_subject(), 'image/png')),
        ('files', ('opaque.png', picture(), 'image/png')),
    ])
    assert response.status_code == 200
    job = wait(api, response.json()['id'])
    return job, f'/api/jobs/{job["id"]}'


def request_for(job, operation, **options):
    return {'items': [{'id': item['id'], 'revision': item['revision']} for item in job['items']],
            'operation': operation, **options}


def test_auto_crop_all_replaces_sizes_and_keeps_sources_and_touchups(api):
    job, path = create_batch(api)
    first = path + '/items/' + job['items'][0]['id']
    original = api.get(first + '/original').content
    edited = api.put(first + '/edits', json={'revision': 0, 'strokes': [
        {'mode': 'wand', 'spans': [[30, 30, 35]]},
    ]})
    assert edited.status_code == 200
    assert api.put(first + '/transform', json={'revision': 1, 'resize': {'width': 10, 'height': 10}}).status_code == 200
    current = api.get(path).json()
    response = api.put(path + '/geometry', json=request_for(current, 'auto'))
    assert response.status_code == 200 and not response.json()['errors']
    assert len(response.json()['items']) == 2
    result = png(api.get(first + '/result'))
    assert result.size == (41, 31) and result.getpixel((0, 0))[3] == 1
    assert result.getpixel((11, 16))[3] == 0
    assert api.get(first + '/original').content == original
    assert api.get(path).json()['items'][0]['strokes']


def test_resize_only_selected_images_and_keep_crops(api):
    job, path = create_batch(api)
    first = path + '/items/' + job['items'][0]['id']
    assert api.put(path + '/geometry', json=request_for(job, 'auto')).status_code == 200
    current = api.get(path).json()
    body = request_for(current, 'resize', width=82, height=82, keep_proportions=True)
    body['items'] = body['items'][:1]
    response = api.put(path + '/geometry', json=body)
    assert not response.json()['errors'] and len(response.json()['items']) == 1
    assert png(api.get(first + '/result')).size == (82, 62)
    current = api.get(path).json()
    assert current['items'][1]['revision'] == 1 and current['items'][1]['output_width'] == 50
    body = request_for(current, 'resize', width=25, height=17, keep_proportions=False)
    body['items'] = body['items'][:1]
    assert api.put(path + '/geometry', json=body).status_code == 200
    assert png(api.get(first + '/result')).size == (25, 17)


def test_square_icons_preview_export_and_reopened_edits_preserve_padding(api, monkeypatch):
    import server
    job, path = create_batch(api)
    body = request_for(job, 'square', size=128, padding=16)
    preview_body = {**body, 'items': body['items'][:1]}
    before = api.get(path).json()
    preview = api.post(path + '/geometry/preview', json=preview_body)
    assert preview.status_code == 200 and preview.headers['X-Output-Width'] == '128'
    assert png(preview).size == (128, 128) and api.get(path).json() == before
    response = api.put(path + '/geometry', json=body)
    assert response.status_code == 200 and not response.json()['errors']
    current = api.get(path).json()
    first = path + '/items/' + job['items'][0]['id']
    assert png(api.get(first + '/result')).tobytes() == png(preview).tobytes()
    with zipfile.ZipFile(io.BytesIO(api.get(path + '/download.zip').content)) as archive:
        manifest = json.loads(archive.read('batch-manifest.json'))
        for item in current['items']:
            exported = api.get(path + '/items/' + item['id'] + '/result?download=true')
            assert archive.read(item['output']) == exported.content
            image = png(exported)
            assert image.size == (128, 128)
            left, top, right, bottom = image.getchannel('A').getbbox()
            assert min(left, top) >= 16 and max(right, bottom) <= 112
        assert all(item['transform']['canvas'] == {'size': 128, 'padding': 16} for item in manifest['items'])
    saved = json.loads((server.DATA / job['id'] / 'manifest.json').read_text(encoding='utf-8'))
    monkeypatch.setattr(server, 'JOBS', {job['id']: saved})
    assert api.put(first + '/edits', json={'revision': 1, 'strokes': [{'mode': 'erase', 'size': 4, 'points': [[40, 30]]}]}).status_code == 200
    assert png(api.get(first + '/result')).size == (128, 128)
    assert api.get(path).json()['items'][0]['transform']['canvas']['padding'] == 16


def test_batch_preflights_every_revision_before_changing_any_image(api):
    job, path = create_batch(api)
    body = request_for(job, 'auto')
    body['items'][1]['revision'] = 99
    assert api.put(path + '/geometry', json=body).status_code == 409
    assert api.get(path).json() == job
    body = request_for(job, 'auto')
    body['items'][1] = body['items'][0]
    assert api.put(path + '/geometry', json=body).status_code == 400
    assert api.get(path).json() == job


@pytest.mark.parametrize('options,status', [
    ({'operation': 'square', 'size': 5000}, 400),
    ({'operation': 'square', 'size': 64, 'padding': 32}, 400),
    ({'operation': 'square', 'padding': -1}, 422),
    ({'operation': 'square', 'padding': True}, 422),
    ({'operation': 'resize', 'width': 6000, 'height': 4001}, 400),
    ({'operation': 'resize', 'width': 1.5}, 422),
    ({'operation': 'resize', 'keep_proportions': 'yes'}, 422),
    ({'operation': 'unknown'}, 422),
    ({'items': []}, 422),
])
def test_invalid_batch_settings_do_not_change_images(api, options, status):
    job, path = create_batch(api)
    body = {**request_for(job, 'auto'), **options}
    assert api.put(path + '/geometry', json=body).status_code == status
    assert api.get(path).json() == job


def test_batch_reports_partial_failures_without_leaking_paths(api, monkeypatch):
    import server
    job, path = create_batch(api)
    original = server.batch_result
    def result(item, directory, request):
        if item['id'] == job['items'][1]['id']:
            raise OSError('Cannot open C:/Users/private-user/artwork.png')
        return original(item, directory, request)
    monkeypatch.setattr(server, 'batch_result', result)
    response = api.put(path + '/geometry', json=request_for(job, 'auto'))
    assert response.status_code == 200
    body = response.json()
    assert len(body['items']) == len(body['errors']) == 1
    assert 'private-user' not in response.text and 'artwork.png' not in response.text
    current = api.get(path).json()
    assert current['items'][0]['revision'] == 1 and current['items'][1]['revision'] == 0


def test_batch_requires_local_token_and_idle_queue(api):
    import server
    job, path = create_batch(api)
    body = request_for(job, 'auto')
    assert api.put(path + '/geometry', json=body, headers={'X-Cutout-Token': 'invalid'}).status_code == 403
    server.JOBS[job['id']]['status'] = 'running'
    assert api.put(path + '/geometry', json=body).status_code == 409


def test_manifest_save_retries_a_temporary_windows_file_lock(api, monkeypatch):
    import server
    job, _ = create_batch(api)
    original_replace = server.os.replace
    attempts, pauses = [], []
    def replace(source, destination):
        attempts.append(destination)
        if len(attempts)<3:
            raise PermissionError('The destination is temporarily in use.')
        return original_replace(source, destination)
    monkeypatch.setattr(server.os, 'replace', replace)
    monkeypatch.setattr(server.time, 'sleep', pauses.append)
    server.persist(job)
    assert len(attempts)==3 and pauses==[.025, .05]
    saved = json.loads((server.DATA/job['id']/'manifest.json').read_text(encoding='utf-8'))
    assert saved==job
