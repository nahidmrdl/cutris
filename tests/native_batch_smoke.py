"""Exercise batch selection, crop, resize, square icons and ZIPs in WebView2.

Set CUTOUT_HOME to empty disposable storage and pass a local JSON report path.
"""
import base64
import io
import json
import os
from pathlib import Path
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
import webview


def main():
    if not os.environ.get('CUTOUT_HOME'):
        raise RuntimeError('Choose disposable CUTOUT_HOME storage.')
    from app_paths import APP_NAME, DATA_DIR
    from desktop import DesktopApi, LocalServer
    if any((DATA_DIR/'jobs').glob('*/manifest.json')):
        raise RuntimeError('Choose empty storage for this check.')
    report = {'ok': False, 'checks': {}}
    destination = Path(sys.argv[1])
    service = LocalServer(desktop_mode=True); service.start()
    bridge = DesktopApi()
    window = webview.create_window(APP_NAME+' — batch verification',service.url,js_api=bridge,width=1280,height=720)
    bridge._window = window
    fixtures=[]
    for name,size,box in [('landscape.png',(320,240),(80,50,239,189)),('portrait.png',(240,320),(30,60,129,259))]:
        image=Image.new('RGBA',size,(0,0,0,0)); ImageDraw.Draw(image).rectangle(box,fill='#9e83d6')
        if name=='landscape.png': image.putpixel((79,49),(158,131,214,1))
        data=io.BytesIO();image.save(data,'PNG');fixtures.append({'name':name,'data':base64.b64encode(data.getvalue()).decode()})

    def wait(expression):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if window.evaluate_js(expression):return
            time.sleep(.12)
        raise RuntimeError('Native batch check timed out.')

    def record(name,result):
        report['checks'][name]=bool(result)
        if not result:raise AssertionError(name)

    def check(name,expression):record(name,window.evaluate_js(expression))
    def click(identifier):window.evaluate_js(f'$({json.dumps(identifier)}).click()')
    def field(identifier,value):
        window.evaluate_js("""(() => {const input=$(%s);input.value=%s;input.dispatchEvent(new Event('input',{bubbles:true}));})()"""%(json.dumps(identifier),json.dumps(str(value))))
    def image(index,kind='result',download=False):
        path=window.evaluate_js(f"imageURL(state.job.items[{index}],{json.dumps(kind)})")
        with urllib.request.urlopen(service.url+path+('&download=true' if download else ''),timeout=15) as response:
            result=Image.open(io.BytesIO(response.read())).convert('RGBA');result.load();return result
    def apply():
        click('batchApply');wait("!state.busy && !$('batchDialog').open")
    def preview():wait("$('batchPreviewSize').textContent.endsWith(' px')")

    def run():
        stage='initialization'
        try:
            wait('Boolean(state.token && window.pywebview?.api)')
            window.evaluate_js("""(() => {
                const transfer=new DataTransfer();
                for(const fixture of %s){const bytes=Uint8Array.from(atob(fixture.data),c=>c.charCodeAt(0));transfer.items.add(new File([bytes],fixture.name,{type:'image/png'}));}
                $('files').files=transfer.files;$('files').dispatchEvent(new Event('change'));
            })()"""%json.dumps(fixtures))
            wait('state.files.length===2 && Boolean(state.original)');click('start')
            wait("state.job?.status==='complete' && Boolean(state.automatic) && !$('batchTools').disabled")
            stage='selection and resize'
            click('batchTools');preview()
            check('all_images_selected',"batchTargets().length===2")
            click('batchSelectNone');check('empty_selection_blocks_apply',"$('batchApply').disabled")
            window.evaluate_js("$('batchImageList').querySelector('input').click()")
            field('batchOperation','resize');field('batchWidth',200);field('batchHeight',100);preview();apply()
            record('resize_selected_image',image(0).size==(133,100))
            record('unselected_image_unchanged',image(1).size==(240,320))
            stage='auto crop all'
            click('batchTools');field('batchOperation','auto');preview();apply()
            record('auto_crop_landscape',image(0).size==(161,141))
            record('auto_crop_portrait',image(1).size==(100,200))
            record('auto_crop_keeps_faint_edge',image(0).getpixel((0,0))[3]==1)
            stage='square canvases and layout'
            click('batchTools');field('batchOperation','square');field('batchSquareSize',512);field('batchPadding',256)
            check('invalid_padding_blocks_apply',"$('batchApply').disabled && !$('batchError').hidden")
            field('batchPadding',16);preview()
            check('square_preview_dimensions',"$('batchPreviewSize').textContent.includes('512 × 512 px')")
            for width,height in [(1280,720),(1024,680),(900,660)]:
                window.resize(width,height);time.sleep(.25)
                check(f'{width}x{height}_batch_actions_visible',"""['batchApply','batchCancel','batchClose'].every(id=>{const e=$(id),r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('button')===e;})""")
            apply()
            for index in (0,1):
                result=image(index,download=True)
                record(f'square_{index}_output_size',result.size==(512,512))
                left,top,right,bottom=result.getchannel('A').getbbox()
                record(f'square_{index}_transparent_padding',min(left,top)>=16 and max(right,bottom)<=496)
            stage='ZIP consistency'
            job_id=window.evaluate_js('state.job.id')
            with urllib.request.urlopen(service.url+f'/api/jobs/{job_id}/download.zip',timeout=15) as response:
                with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                    for name in archive.namelist()[:-1]:
                        record('zip_'+name,Image.open(io.BytesIO(archive.read(name))).size==(512,512))
            stage='editing after square canvas'
            click('eraseTool');check('editing_keeps_source_coordinates','canvas.width===320 && canvas.height===240')
            window.evaluate_js("state.strokes.push({mode:'erase',size:8,points:[[120,120]]});state.dirty=true;renderCanvas();updateTools();$('save').click()")
            wait('!state.busy && !state.dirty');click('doneEditing')
            record('touchup_keeps_square_canvas',image(0).size==(512,512))
            click('geometryButton');wait("$('geometryDialog').open")
            check('square_canvas_reopens',"!$('geometryCanvasSettings').hidden && $('geometryCanvasInfo').textContent.includes('512 × 512')")
            click('geometryRemoveCanvas');click('geometryApply');wait("!state.busy && !$('geometryDialog').open")
            record('square_canvas_can_be_removed',image(0).size==(161,141))
            record('original_canvas_preserved',image(0,'original').size==(320,240))
            report['ok']=all(report['checks'].values())
        except Exception as error:
            report.update(error=type(error).__name__,stage=stage)
        finally:
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            window.confirm_close=False;window.destroy()
    try:webview.start(run,gui='edgechromium',private_mode=True,storage_path=str(DATA_DIR/'webview-batch-smoke'))
    finally:service.stop();service.module.POOL.shutdown(wait=True,cancel_futures=True)
    return 0 if report['ok'] else 1


if __name__=='__main__':raise SystemExit(main())
