"""Actual production component JavaScript, independent of server-only AppTest."""

import ast
from pathlib import Path

from playwright.sync_api import sync_playwright

from modules import workspace_ui


def test_summary_tile_click_and_keyboard_emit_one_trigger_each():
    tree = ast.parse(Path(workspace_ui.__file__).read_text(encoding='utf-8'))
    declaration = next(
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'SUMMARY_TILE_TAP_COMPONENT'
                for target in node.targets)
    )
    assets = {kw.arg: ast.literal_eval(kw.value) for kw in declaration.keywords}
    html = workspace_ui.summary_tiles_html([
        {'label': 'Power Rank', 'value': '#2', 'detail': 'League comparison'},
        {'label': 'Static metric', 'value': '10', 'tappable': False},
    ])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(assets['html'])
        page.add_script_tag(content=assets['js'].replace(
            'export default function(component)', 'window.initTiles = function(component)'
        ))
        page.evaluate('''html => {
            window.triggers = [];
            window.initTiles({data: {html}, parentElement: document.body,
                setTriggerValue: (name, payload) => window.triggers.push([name, payload.index])});
        }''', html)
        tile = page.locator('.summary-tile-tappable')
        tile.click()
        tile.press('Enter')
        tile.press('Space')
        assert page.evaluate('window.triggers') == [['clicked', '0']] * 3
        page.get_by_text('Static metric', exact=True).click()
        assert page.evaluate('window.triggers.length') == 3
        browser.close()
