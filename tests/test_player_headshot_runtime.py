"""Execute the canonical markup, CSS and runtime in Chromium."""
from playwright.sync_api import sync_playwright

from modules.app_styles import APP_CSS
from modules.player_profile_ui import avatar_html
from modules.player_headshot_runtime import HEADSHOT_RUNTIME_JS

VALID = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="8" height="8"%3E%3Crect width="8" height="8" fill="red"/%3E%3C/svg%3E'
BROKEN = 'data:image/png;base64,broken'


def test_cached_dynamic_broken_and_missing_headshots():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        try:
            page.set_content('<style>' + APP_CSS + '</style><div id="cached">' + avatar_html(VALID, 'AB') + '</div>')
            page.wait_for_function('document.querySelector("img").complete')
            assert page.locator('img').evaluate('(img)=>img.naturalWidth') > 0
            page.evaluate('(' + HEADSHOT_RUNTIME_JS.replace('export default ', '') + ')({})')
            assert page.locator('#cached img').get_attribute('class').endswith('is-loaded')
            assert not page.locator('#cached .dg-player-headshot-fallback').is_visible()
            # New route DOM after listener registration; capture listeners survive.
            for name, url in [('valid', VALID), ('broken', BROKEN), ('missing', '')]:
                page.evaluate('html=>document.body.insertAdjacentHTML("beforeend",html)', '<div id="' + name + '">' + avatar_html(url, 'AB') + '</div>')
            page.wait_for_function('document.querySelector("#valid img")?.classList.contains("is-loaded")')
            page.wait_for_function('!document.querySelector("#broken img")')
            assert not page.locator('#valid .dg-player-headshot-fallback').is_visible()
            assert page.locator('#broken .dg-player-headshot-fallback').is_visible()
            assert page.locator('#missing .dg-player-headshot-fallback').is_visible()
            assert not errors, errors
        finally:
            browser.close()


def test_streamlit_rerun_modal_fallback_and_alert_source(tmp_path):
    import subprocess
    import sys
    import socket
    import time
    from pathlib import Path
    app = tmp_path / 'images.py'
    app.write_text('''import sys
sys.path.insert(0, ROOT)
import streamlit as st
from modules.player_headshot_runtime import render_player_headshot_runtime
from modules.player_profile_ui import avatar_html
from modules.ui_modal import ModalListItem, _list_item_avatar_html
from modules.alerts_activity_ui import timeline_row_html
render_player_headshot_runtime()
if st.button("New image"):
    st.session_state['image_run'] = st.session_state.get('image_run', 0) + 1
run = st.session_state.get('image_run', 0)
st.markdown(avatar_html('https://example.com/image'+str(run)+'.svg', 'AB'), unsafe_allow_html=True)
st.markdown(_list_item_avatar_html(ModalListItem(title='Fallback',avatar_url='https://example.com/broken.png')),unsafe_allow_html=True)
st.markdown(timeline_row_html({'headline':'Source','source_url':'https://example.com/source'}),unsafe_allow_html=True)
st.caption('Image run: '+str(run))
'''.replace('ROOT', repr(str(Path(__file__).resolve().parents[1]))), encoding='utf-8')
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    with (tmp_path / 'server.log').open('w') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', str(app), '--server.headless=true', f'--server.port={port}'], stdout=log, stderr=log)
        try:
            import urllib.request
            for _ in range(100):
                try:
                    urllib.request.urlopen(f'http://localhost:{port}/_stcore/health', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                page.route('https://example.com/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body='<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>' if r.request.url.endswith('.svg') else 'broken'))
                try:
                    page.goto(f'http://localhost:{port}')
                    page.wait_for_selector('.dg-player-headshot-image.is-loaded')
                    page.wait_for_function('!document.querySelector(".dg-modal-list-avatar img")')
                    assert page.locator('.dg-modal-list-avatar-fallback').is_visible()
                    page.get_by_role('button', name='New image').click()
                    page.wait_for_selector('img.is-loaded[src$="image1.svg"]')
                    with page.expect_popup() as popup:
                        page.get_by_text('Read source').click()
                    assert popup.value.url == 'https://example.com/source'
                    assert page.get_by_text('Image run: 1', exact=True).is_visible()
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            proc.terminate()
            proc.wait(timeout=8)
