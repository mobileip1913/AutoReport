import re
import urllib.request

html = urllib.request.urlopen("http://127.0.0.1:8081/mappings").read().decode()
print("btn-edit:", html.count("btn-edit"))
print("btn-delete-mapping:", html.count("btn-delete-mapping"))
scripts = re.findall(r'src="(/static/[^"]+)"', html)
print("scripts:", scripts)
for name in ["DATA_SOURCE_META", "DS_SETTINGS", "REUSE_FIELDS_BY_DS"]:
    m = re.search(rf"window\.{name} = (.+?);\s*</script>", html, re.S)
    if not m:
        print(name, "MISSING")
        continue
    snippet = m.group(1)[:80]
    print(name, "ok", snippet[:60] + "...")
