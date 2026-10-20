"""Check real WebView2 layouts at laptop, desktop, and narrow viewport sizes.

Set CUTOUT_HOME to an empty disposable folder and pass a JSON report path.
Generated transparent artwork exercises layout and crop controls without AI.
"""
from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw
import webview


def main():
    if not os.environ.get('CUTOUT_HOME'):
        raise RuntimeError('Set CUTOUT_HOME to empty disposable test storage.')
    from app_paths import APP_NAME, DATA_DIR
    from desktop import DesktopApi, LocalServer

    if any((DATA_DIR / 'jobs').glob('*/manifest.json')):
        raise RuntimeError('Choose empty storage for this isolated check.')
    destination = Path(sys.argv[1])
    report = {'ok': False, 'checks': {}, 'viewports': []}
    service = LocalServer(desktop_mode=True)
    service.start()
    bridge = DesktopApi()
    window = webview.create_window(APP_NAME + ' — layout verification', service.url,
                                   js_api=bridge, width=1280, height=720)
    bridge._window = window
    fixture = Image.new('RGBA', (320, 240), (0, 0, 0, 0))
    ImageDraw.Draw(fixture).rounded_rectangle((80, 50, 239, 189), radius=24, fill='#9e83d6')
    fixture.putpixel((79, 49), (158, 131, 214, 1))
    payload = io.BytesIO()
    fixture.save(payload, 'PNG')
    encoded = base64.b64encode(payload.getvalue()).decode('ascii')

    def wait(expression, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if window.evaluate_js(expression):
                return
            time.sleep(.12)
        raise RuntimeError('Layout verification timed out.')

    def check(name, expression):
        result = bool(window.evaluate_js(expression))
        report['checks'][name] = result
        if not result:
            raise AssertionError(name)

    def resize(width, height):
        window.resize(width, height)
        # Wait for actual WebView resize and its ResizeObserver/layout pass.
        time.sleep(.3)
        viewport = window.evaluate_js('({width:innerWidth,height:innerHeight})')
        report['viewports'].append(viewport)
        return f"{viewport['width']}x{viewport['height']}"

    def visible(ids):
        return """(() => {
            const ids=%s;
            return ids.every(id => {
                const element=$(id), r=element.getBoundingClientRect();
                return r.width>0 && r.height>0 && r.top>=0 && r.bottom<=innerHeight
                    && r.left>=0 && r.right<=innerWidth
                    && document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('button')===element;
            });
        })()""" % json.dumps(ids)

    def run():
        stage = 'initialization'
        try:
            wait('Boolean(state.token && window.pywebview?.api?.document_state)')
            stage = 'laptop setup layout'
            resize(1024, 680)
            check('setup_start_visible', visible(['start']))
            check('setup_no_horizontal_overflow', 'document.documentElement.scrollWidth<=innerWidth')
            window.evaluate_js("""(() => {
                const bytes=Uint8Array.from(atob(%s),c=>c.charCodeAt(0));
                const transfer=new DataTransfer();
                transfer.items.add(new File([bytes],'layout-fixture.png',{type:'image/png'}));
                $('files').files=transfer.files;$('files').dispatchEvent(new Event('change'));
            })()""" % json.dumps(encoded))
            wait('state.files.length===1 && Boolean(state.original)')
            window.evaluate_js("$('start').click()")
            wait("state.job?.status==='complete' && Boolean(state.automatic)")
            stage = 'editing layout matrix'
            for width, height in [(1920,1080),(1440,900),(1366,768),(1280,720),(1100,700),(1024,680),(900,660)]:
                key = resize(width, height)
                check(key+'_no_page_scroll', 'document.documentElement.scrollWidth<=innerWidth && document.documentElement.scrollHeight<=innerHeight+1')
                check(key+'_editing_actions_visible', visible(['eraseTool','restoreTool','wandTool','geometryButton','save','download']))
                check(key+'_preview_usable', "$('viewport').clientHeight>=100")
                window.evaluate_js("$('wandTool').click()")
                check(key+'_wand_actions_visible', visible(['eraseSelection','clearSelection','geometryButton','download']))
                window.evaluate_js("document.querySelector('.review-notes').open=true")
                check(key+'_wand_and_notes_keep_actions_visible', visible(['eraseSelection','clearSelection','geometryButton','download']))
                window.evaluate_js("$('doneEditing').click();document.querySelector('.review-notes').open=true")
                check(key+'_notes_keep_actions_visible', visible(['geometryButton','save','download']))
                window.evaluate_js("document.querySelector('.review-notes').open=false;$('geometryButton').click()")
                wait("$('geometryDialog').open")
                check(key+'_crop_apply_visible', visible(['geometryApply','geometryCancel','geometryClose']))
                check(key+'_crop_preview_usable', "$('geometryStage').clientHeight>=300")
                check(key+'_auto_selected', "$('geometryAutoCrop').getAttribute('aria-pressed')==='true'")
                window.evaluate_js("$('geometryCancel').click()")

            stage = 'automatic to manual transitions'
            resize(1280,720)
            window.evaluate_js("$('geometryButton').click()")
            check('auto_crop_runs_on_open', "geometryState.mode==='auto' && $('geometryCropX').value==='79' && $('geometryCropY').value==='49'")
            window.evaluate_js("$('geometryCropX').value=80;$('geometryCropX').dispatchEvent(new Event('input'))")
            check('crop_input_switches_manual', "geometryState.mode==='manual' && $('geometryManualCrop').getAttribute('aria-pressed')==='true'")
            window.evaluate_js("$('geometryAutoCrop').click();$('geometryResizeEnabled').click()")
            check('resize_switches_manual', "geometryState.mode==='manual'")
            window.evaluate_js("$('geometryAutoCrop').click();$('geometryResizeWidth').value=322;$('geometryResizeWidth').dispatchEvent(new Event('input'))")
            check('resize_input_switches_manual', "geometryState.mode==='manual'")
            window.evaluate_js("$('geometryResetSize').click();$('geometryAutoCrop').click()")
            window.evaluate_js("""(() => {
                const r=$('geometryCanvasWrap').getBoundingClientRect(),s=geometryState.scale;
                $('geometryCropBox').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:41,button:0,clientX:r.x+160*s,clientY:r.y+120*s}));
                $('geometryStage').dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:41,button:0}));
            })()""")
            check('touching_auto_crop_switches_manual', "geometryState.mode==='manual'")
            window.evaluate_js("$('geometryCancel').click()")
            check('close_buttons_are_accessible_icons', "[...document.querySelectorAll('.dialog-close')].length===3 && [...document.querySelectorAll('.dialog-close')].every(b=>b.getAttribute('aria-label') && b.querySelector('svg') && !b.textContent.trim())")

            stage = 'narrow viewport flow'
            for width, height in [(740,900),(390,844)]:
                key = resize(width,height)
                check(key+'_no_horizontal_overflow', 'document.documentElement.scrollWidth<=innerWidth')
                window.evaluate_js("$('geometryButton').click()")
                check(key+'_crop_no_horizontal_overflow', "$('geometryDialog').scrollWidth<=$('geometryDialog').clientWidth")
                window.evaluate_js("$('geometryCancel').click()")
            report['ok'] = all(report['checks'].values())
        except Exception as error:
            report['error'] = type(error).__name__
            report['stage'] = stage
            report['layout'] = window.evaluate_js("""(() => {
                const result={viewport:[innerWidth,innerHeight],page:[document.documentElement.scrollWidth,document.documentElement.scrollHeight]};
                for(const selector of ['.preview-panel','.touchup','.edit-actions','#viewport','#geometryDialog','.geometry-footer']){
                    const r=document.querySelector(selector).getBoundingClientRect();result[selector]={x:r.x,y:r.y,width:r.width,height:r.height};
                }return result;
            })()""")
        finally:
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            window.confirm_close=False
            window.destroy()

    try:
        webview.start(run,gui='edgechromium',private_mode=True,storage_path=str(DATA_DIR/'webview-layout-smoke'))
    finally:
        service.stop()
        service.module.POOL.shutdown(wait=True,cancel_futures=True)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
