"""Exercise the public batch commands against a disposable, textured Blender scene."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def make_scene(folder):
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    cube = scene.objects["Cube"]
    material = bpy.data.materials.new("Surface")
    material.use_nodes = True
    cube.data.materials.clear()
    cube.data.materials.append(material)
    tree = material.node_tree
    group = bpy.data.node_groups.new("Surface or alternative", "ShaderNodeTree")
    for name in ("Surface", "Unused"):
        group.interface.new_socket(name=name, in_out="INPUT", socket_type="NodeSocketColor")
    group.interface.new_socket(name="Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    source = group.nodes.new("NodeGroupInput")
    output = group.nodes.new("NodeGroupOutput")
    group.links.new(source.outputs["Surface"], output.inputs["Color"])
    choose = tree.nodes.new("ShaderNodeGroup")
    choose.node_tree = group
    for name in ("Surface", "Unused"):
        path = folder / (name + ".png")
        generated = bpy.data.images.new("Swatch", 2, 2)
        generated.generated_color = (0.8, 0.25, 0.15, 1)
        generated.filepath_raw = str(path)
        generated.file_format = "PNG"
        generated.save()
        bpy.data.images.remove(generated)
        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.name = name + " file"
        texture.image = bpy.data.images.load(str(path))
        tree.links.new(texture.outputs["Color"], choose.inputs[name])
    tree.links.new(choose.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    # The alternative material has no assigned faces on the first object.
    later_material = material.copy()
    later_tree = later_material.node_tree
    later_tree.links.new(later_tree.nodes["Unused file"].outputs["Color"],
                         later_tree.nodes["Principled BSDF"].inputs["Base Color"])
    cube.data.materials.append(later_material)
    later = cube.copy()
    later.data = cube.data.copy()
    scene.collection.objects.link(later)
    later.data.materials.clear()
    later.data.materials.append(later_material)
    later.hide_render = True
    later.keyframe_insert(data_path="hide_render", frame=1)
    later.hide_render = False
    later.keyframe_insert(data_path="hide_render", frame=2)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / "model.blend"))


def verify(blender):
    batch = Path(__file__).resolve().parents[1] / "scripts" / "render_batch.py"
    with tempfile.TemporaryDirectory(prefix="cg-dependencies-") as temporary:
        folder = Path(temporary)
        subprocess.run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                        str(Path(__file__).resolve()), "--", str(folder)], check=True)
        manifest = folder / "batch.json"
        job = {"id": "surface", "blend": "model.blend", "scene": "Scene", "camera": "Camera",
               "resolution": [32, 32], "frame": 1}
        manifest.write_text(json.dumps({"version": 1, "jobs": [job]}), encoding="utf-8")

        def run(mode, label, expected):
            out = folder / label
            result = subprocess.run([sys.executable, str(batch), mode, str(manifest), "--blender", blender, "--out", str(out)])
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))["jobs"]["surface"]
            assert report["status"] == expected, report
            assert result.returncode == (0 if expected == "ok" else 1)
            assert (out / "shots" / "surface" / "still.png").exists() == (mode == "render" and expected == "ok")
            return report

        texture = folder / "Surface.png"
        original = texture.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        (folder / "Unused.png").unlink()
        valid = run("render", "unused-missing", "ok")
        assert any("Unused" in note for note in valid["missing_source_warnings"])
        assert [entry["sha256"] for entry in valid["dependencies"]] == [digest]
        texture.unlink()
        missing = run("check", "required-check", "needs_review")
        assert missing["dependencies"][0]["status"] == "unavailable"
        run("render", "required-render", "needs_review")
        texture.write_bytes(original)
        restored = run("render", "restored", "ok")
        assert restored["dependencies"] == valid["dependencies"]
        del job["frame"]
        job["range"] = [1, 2]
        manifest.write_text(json.dumps({"version": 1, "jobs": [job]}), encoding="utf-8")
        late = run("render", "late-required", "needs_review")
        assert any(entry["first_frame"] == 2 and entry["status"] == "unavailable" for entry in late["dependencies"])
        assert not (folder / "late-required" / "shots" / "surface").exists()
        assert (folder / "late-required" / "work" / "surface" / "images" / "frame_000001.png").exists()
        del job["range"]
        job["frame"] = 1
        job["required_files"] = ["external-cache.bin"]
        manifest.write_text(json.dumps({"version": 1, "jobs": [job]}), encoding="utf-8")
        declared = run("check", "declared-required", "needs_review")
        assert any(entry["used_by"] == ["required_files"] for entry in declared["dependencies"])
    print("Passed dependency checks including missing, unconnected, declared, and restored files.")


if __name__ == "__main__":
    if "--" in sys.argv:
        make_scene(Path(sys.argv[sys.argv.index("--") + 1]))
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--blender", default="blender")
        verify(parser.parse_args().blender)
