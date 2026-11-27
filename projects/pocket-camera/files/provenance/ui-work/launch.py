from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[2]
base=root.parent
script=Path(__file__).with_name("capture.py")
sources={"early":base/"dji-osmo-pocket-4p/DJI-Osmo-Pocket-4P-Classic-Black.blend",
         "final":base/"dji-osmo-pocket-4p-v7/DJI-Osmo-Pocket-4P-V7-Final.blend",
         "film":base/"dji-osmo-pocket-4p-cg15/Pulse-15s.blend"}
sources["studio"]=sources["final"]
for mode in sys.argv[1:]:
    with (script.parent/(mode+"-console.txt")).open("wb") as output:
        subprocess.run(["D:/oc/render-workbench/apps/blender-5.2.3-windows-x64/blender.exe",
            "--factory-startup","-p","40","70","2260","1280",str(sources[mode]),"-P",str(script),"--",mode],
            stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW,timeout=180,check=True)

