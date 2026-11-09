"""Rig agent page. No database and no network."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "workspace" / "app" / "rig"


def _source() -> str:
    parts = [path.read_text(encoding="utf-8") for path in sorted(PAGE.rglob("*")) if path.is_file()]
    return "\n".join(parts)


def test_panel_is_fixed_and_split_with_the_account_nav():
    css = (PAGE / "rig.css").read_text(encoding="utf-8")
    assert ".panel" in css
    assert "position: fixed" in css
    assert "overflow: hidden" in css
    assert ".body" in css
    assert "overflow: auto" in css
    source = _source()
    assert "panel-top" in source
    assert "panel-own" in source
    assert "panel-bottom" in source
    assert "tervory-logo-reversed.png" in source
    lab = (PAGE / "lab.tsx").read_text(encoding="utf-8")
    panel = lab.split('<aside className="panel"', 1)[1].split("</aside>", 1)[0]
    assert "rig-on-dark.png" in panel
    assert panel.index("rig-on-dark.png") < panel.index("panel-top")
    assert panel.index("panel-own") < panel.index("tervory-logo-reversed.png")
    assert panel.index("tervory-logo-reversed.png") < panel.index("ACCOUNT_BOTTOM")
    assert (ROOT / "workspace" / "public" / "brand" / "rig-on-dark.png").is_file()
    assert "Rig logo, coming later" not in source
    assert "headerLinks" not in source
    assert "Last refreshed" not in source
    assert ">Workspace<" not in source
    assert ">Help<" not in source
    page = (PAGE / "page.tsx").read_text(encoding="utf-8")
    assert "headerLinks" not in page
    assert 'accountName = "Your account"' in page
    assert 'accountName = "Account name"' not in page
    nav = (PAGE / "copy.ts").read_text(encoding="utf-8")
    for label in ("Dashboard", "Projects", "Chats", "Settings", "Support"):
        assert f'label: "{label}"' in nav
    for gone in ("Chat", "Tasks", "Data", "Ledger"):
        assert f'label: "{gone}"' not in nav
    assert "RIG" in source
    assert "Plugins" in source
    assert nav.index('label: "Search"') < nav.index('label: "Overview"')
    assert "TABS.map" in (PAGE / "lab.tsx").read_text(encoding="utf-8")
    assert "Integrations" not in source


def test_plugins_is_a_tab_and_sources_means_answer_references():
    source = _source()
    assert 'label: "Plugins"' not in source or "Plugins" in source
    assert ">Plugins<" in source
    assert 'href="/sources"' not in source
    assert "API keys" in source
    assert "MCP connections" in source
    assert "Source links" in source
    lab = (PAGE / "lab.tsx").read_text(encoding="utf-8")
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    copy = (PAGE / "copy.ts").read_text(encoding="utf-8")
    for text in (lab, plugins, copy):
        assert "Sources" not in text.replace("Source links", "")
    ask = (PAGE / "search-view.tsx").read_text(encoding="utf-8")
    assert ">Sources<" in ask
    assert "Ask Rig" in ask
    assert "Send" in ask


def test_secrets_are_dots_and_example_products_stay_out():
    source = _source()
    assert "•••• saved 17 Oct" not in source
    assert 'MASK = "••••••••"' in source
    assert "rk_pub_" not in source
    assert "api_key=" not in source.lower()
    assert "sk-" not in source
    assert "Example Rifle" not in source
    assert "ExampleBrand" not in source
    assert "/v1/rig/admin" not in source
    assert "/v1/rig/search" in source
    assert "/v1/rig/ask" in source
    assert "I don't know" in source


def test_plugins_vault_starts_off_and_is_rig_only():
    source = _source()
    assert 'VAULT_OFF_MESSAGE = "This vault is off. Turn it on in Tank."' in source
    assert 'className="vault-off"' in (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    assert "if (!raw.enabled) return offPanel()" in source
    vaults = set(__import__("re").findall(r"[A-Za-z_]+\.vault", source))
    assert vaults == {"rig.vault"}
    server = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    assert 'const VAULT = "rig.vault"' in server
    assert 'const SQUAD = "rig"' in server
    assert "/switch" not in source
    assert "admin/vaults" not in source
    assert "enabled" not in server


def test_vault_keys_stay_masked_and_calls_stay_on_the_server():
    model = (PAGE / "vault-model.ts").read_text(encoding="utf-8")
    plugins = (PAGE / "plugins.tsx").read_text(encoding="utf-8")
    actions = (PAGE / "plugin-actions.ts").read_text(encoding="utf-8")
    server = (PAGE / "vault-server.ts").read_text(encoding="utf-8")
    assert "value?" not in model and "value:" not in model and ".value" not in model
    assert "content" not in model
    assert ".token" not in model
    assert "row.mask" in plugins
    assert "type=\"password\"" in plugins
    assert "./vault-server" not in plugins
    assert "fetch(" not in plugins
    assert actions.startswith('"use server"')
    assert "x-tank-key" in server
    assert "TANK_API_KEY" in server
    assert "/v1/vaults/" in server
    assert "fetch(" in server
    for path in sorted(PAGE.rglob("*")):
        if not path.is_file() or path.name == "vault-server.ts":
            continue
        text = path.read_text(encoding="utf-8")
        assert "x-tank-key" not in text
        assert "TANK_API_KEY" not in text
        assert "/v1/vaults/" not in text


def test_one_red_button_style():
    css = (PAGE / "rig.css").read_text(encoding="utf-8").lower()
    assert css.count("#e80008") == 1
    assert ".primary" in css
    assert "search" in (PAGE / "search-view.tsx").read_text(encoding="utf-8").lower()


def test_overview_and_search_show_real_data_or_a_specific_line_in_every_state():
    """Fixture clients (full, partial, empty, unanswered) in a real browser, offline."""
    import subprocess

    result = subprocess.run(["node", "tests/rig_overview_states_browser.mjs"], cwd=ROOT,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: Rig overview and search" in result.stdout
    lab = (PAGE / "lab.tsx").read_text(encoding="utf-8")
    assert "BUILT" not in lab
    assert '<h2>Next step</h2>\n            </section>' not in lab
    assert "<footer className=\"foot\">\n            </footer>" not in lab


def test_ask_sends_the_chosen_product_through_tank_and_names_no_model():
    import subprocess

    script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const wr=require('node:module').createRequire(process.cwd()+'/workspace/package.json'),ts=wr('typescript');
const calls=[];
const tank={rigProxy:async(pathname,tenant,init)=>{calls.push([pathname,tenant,init]);
  if(pathname==='/v1/rig/search')return {exact_match:true,results:[{id:'FX-200'}]};
  if(pathname==='/v1/rig/ask')return {answer:'Fits.',cites:['FX-G1']};
  return {name:'Fixture grip',price:{amount:300}};}};
const file=path.resolve('workspace/app/rig/rig-server.ts');
const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const mod={exports:{}};new Function('require','module','exports',code)(n=>n==='@/lib/tank'?tank:wr(n),mod,mod.exports);
(async()=>{
 let answer=await mod.exports.rigCall('tenant-a','ask',{question:'Does it fit?',product_id:'FX-100'});
 assert.deepEqual(calls.map(c=>c[0]),['/v1/rig/ask','/v1/rig/products/FX-G1']);
 assert.deepEqual(calls[0][2],{method:'POST',body:{product_id:'FX-100',question:'Does it fit?'}});
 assert.equal(answer.answer,'Fits.');assert.equal(answer.sources[0].title,'Fixture grip · R300');
 calls.length=0;
 answer=await mod.exports.rigCall('tenant-a','ask',{question:'Does it fit?',product_id:''});
 assert.deepEqual(calls.map(c=>c[0]),['/v1/rig/search','/v1/rig/ask','/v1/rig/products/FX-G1']);
 assert.equal(calls[1][2].body.product_id,'FX-200');
 calls.length=0;
 answer=await mod.exports.rigCall('tenant-a','ask',{question:'Does it fit?',product_id:'../bad id'});
 assert.equal(calls[0][0],'/v1/rig/search');assert.equal(calls[1][2].body.product_id,'FX-200');
 console.log('PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    server = (PAGE / "rig-server.ts").read_text(encoding="utf-8")
    for named in ("gpt", "claude", "llama", "qwen", "model:"):
        assert named not in server.lower()


def test_room_status_counts_only_and_why_few_products_show():
    import sys

    sys.path.insert(0, str(ROOT / "agents" / "rig"))
    from rigbox.catalogue_status import catalogue_status

    products = [{"sku": f"P{n}", "active": n < 3} for n in range(120)]
    fits = [{"part_sku": "A", "source": "import"}, {"part_sku": "B", "source": "suggested", "approved": False},
            {"part_sku": "C", "source": "suggested", "approved": True}, {"part_sku": "D", "source": "rejected"}]
    feeds = [{"format": "csv", "url": "https://feed.example.invalid/private.csv", "currency": "USD"}]
    retailer = {"email": "quotes@example.invalid", "webhook": None}
    status = catalogue_status(products, fits, feeds, retailer)
    assert status == {"products": 120, "active": 3, "fits": 4, "approved_fits": 2, "waiting_fits": 1,
                      "feeds": 1, "delivery": True}
    assert "example.invalid" not in str(status)
    assert catalogue_status([], [], [], None) == {"products": 0, "active": 0, "fits": 0, "approved_fits": 0,
                                                  "waiting_fits": 0, "feeds": 0, "delivery": False}
