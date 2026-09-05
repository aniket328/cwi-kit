"""cwi-kit tests: temp trees, temp bare remotes, stdlib unittest only."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))

from cwi_kit import bootstrap, doctor, frontmatter, gitx, manifest, registry, room, sync, ws  # noqa: E402


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True)


def make_repo(path, remote=None, commit=True):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "-b", "main"], path)
    git(["config", "user.email", "t@cwi.test"], path)
    git(["config", "user.name", "cwi-test"], path)
    if remote:
        git(["remote", "add", "origin", str(remote)], path)
    if commit:
        (path / "README.md").write_text("x\n")
        git(["add", "-A"], path)
        git(["commit", "-q", "-m", "init"], path)
    return path


def make_bare(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q", "--bare", "-b", "main"], path)
    return path


def configure_identity(repo):
    git(["config", "user.email", "t@cwi.test"], repo)
    git(["config", "user.name", "cwi-test"], repo)


class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "CWI"
        for g in ("products", "kits", "rsi", "clients", "exp", "operation-room"):
            (self.root / g).mkdir(parents=True)
        (self.root / "_meta.md").write_text("# root\n")
        self.projects = Path(self.tmp.name) / "claude-projects"
        self.projects.mkdir()

    def tearDown(self):
        self.tmp.cleanup()


class TestFrontmatter(unittest.TestCase):
    def test_parse_and_render(self):
        text = "---\nkind: state\naudience: client\ncadence: snapshot\nupdated: 2026-09-05\n---\n# hi\nbody\n"
        meta, body = frontmatter.parse(text)
        self.assertEqual(meta["kind"], "state")
        self.assertEqual(body, "# hi\nbody\n")
        self.assertEqual(frontmatter.render(meta, body), text)

    def test_missing(self):
        self.assertEqual(frontmatter.parse("# no fm\n"), ({}, "# no fm\n"))


class TestWsInit(TempTree):
    def test_init_repo_mode_idempotent(self):
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme")
        self.assertEqual(r, (wsdir / "ops").resolve())
        for f in ("_meta.md", "STATE.md", "MEMORY.md", "AGENDA.md", "manifest.json", ".gitignore"):
            self.assertTrue((r / f).is_file(), f)
        for d in ("log", "runbooks", "memory"):
            self.assertTrue((r / d).is_dir(), d)
        self.assertTrue((wsdir / "_meta.md").is_file())
        self.assertTrue((wsdir / "CLAUDE.md").read_text().startswith("<!-- GENERATED"))
        self.assertTrue((wsdir / ".claude" / "settings.json").is_file())
        (r / "STATE.md").write_text((r / "STATE.md").read_text() + "\n## Live\n- api v2\n")
        before = (r / "STATE.md").read_text()
        ws.init(wsdir, "acme", "client", "acme")
        self.assertEqual((r / "STATE.md").read_text(), before, "templates must not overwrite")
        self.assertEqual(room.check(r), [])
        m = manifest.load(r)
        self.assertEqual(m["audience"], "client")

    def test_embedded_needs_repo(self):
        wsdir = self.root / "products" / "solo"
        wsdir.mkdir()
        with self.assertRaises(ws.WsError):
            ws.init(wsdir, "solo", "product", "cwi", mode="embedded")
        make_repo(wsdir)
        r = ws.init(wsdir, "solo", "product", "cwi", mode="embedded")
        self.assertEqual(r, wsdir.resolve())
        self.assertEqual(room.check(r), [])

    def test_settings_merge_keeps_other_keys(self):
        wsdir = self.root / "clients" / "acme"
        (wsdir / ".claude").mkdir(parents=True)
        (wsdir / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]},
                                                                       "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}))
        ws.init(wsdir, "acme", "client", "acme")
        data = json.loads((wsdir / ".claude" / "settings.json").read_text())
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
        cmds = [h["command"] for e in data["hooks"]["Stop"] for h in e["hooks"]]
        self.assertIn("echo hi", cmds)
        self.assertIn("cwi hook stop", cmds)
        self.assertIn("SessionEnd", data["hooks"])
        codex = json.loads((wsdir / ".codex" / "hooks.json").read_text())
        self.assertEqual({k for k in codex["hooks"]}, {"SessionStart", "Stop", "SessionEnd"})
        end = codex["hooks"]["SessionEnd"][0]["hooks"][0]
        self.assertEqual(end["command"], "cwi hook end")
        self.assertGreaterEqual(end["timeout"], 60, "Codex SessionEnd defaults to 1s; push needs more")
        self.assertIn("hooks = true", (wsdir / ".codex" / "config.toml").read_text())


class TestRoomCheck(TempTree):
    def setUp(self):
        super().setUp()
        self.wsdir = self.root / "products" / "widget"
        self.room = ws.init(self.wsdir, "widget", "product", "cwi")

    def test_missing_core(self):
        (self.room / "STATE.md").unlink()
        self.assertIn("missing core file STATE.md", room.check(self.room))

    def test_wrong_kind(self):
        p = self.room / "STATE.md"
        p.write_text(p.read_text().replace("kind: state", "kind: memory"))
        self.assertTrue(any("kind must be 'state'" in e for e in room.check(self.room)))

    def test_undeclared_then_declared_shelf(self):
        (self.room / "randomstuff").mkdir()
        errs = room.check(self.room)
        self.assertTrue(any("undeclared shelf 'randomstuff'" in e for e in errs))
        m = manifest.load(self.room)
        m["shelves_extra"].append({"name": "randomstuff", "why": "test"})
        manifest.save(self.room, m)
        self.assertEqual(room.check(self.room), [])

    def test_audience_rule(self):
        m = manifest.load(self.room)
        m["audience"] = "client"
        manifest.save(self.room, m)
        errs = room.check(self.room)
        self.assertTrue(any("only for workspaces under clients/" in e for e in errs))


class TestSync(TempTree):
    def test_room_commits_and_pushes_code_untouched(self):
        bare = make_bare(Path(self.tmp.name) / "remotes" / "acme-ops.git")
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme", remote=str(bare))
        configure_identity(r)
        code = make_repo(wsdir / "app", remote=make_bare(Path(self.tmp.name) / "remotes" / "app.git"))
        git(["push", "-q", "-u", "origin", "main"], code)
        (code / "dirty.txt").write_text("uncommitted\n")
        m = manifest.load(r)
        m["repos"].append({"path": "app", "remote": str(code), "role": "code"})
        manifest.save(r, m)
        lines, ok = sync.sync_ws(r)
        self.assertTrue(ok, lines)
        self.assertTrue(any(l.startswith("room: committed") for l in lines), lines)
        self.assertIn("room: pushed", lines)
        self.assertTrue(any("repo app: dirty, left alone" in l for l in lines), lines)
        self.assertTrue((code / "dirty.txt").exists())
        self.assertEqual(git(["status", "--porcelain"], code).stdout.strip(), "?? dirty.txt")
        self.assertEqual(git(["rev-list", "--count", "HEAD"], bare).stdout.strip(), "1")
        lines2, ok2 = sync.sync_ws(r)
        self.assertIn("room: clean", lines2)

    def test_embedded_leaves_unrelated_dirty_file(self):
        wsdir = make_repo(self.root / "products" / "solo")
        configure_identity(wsdir)
        r = ws.init(wsdir, "solo", "product", "cwi", mode="embedded")
        (wsdir / "src.py").write_text("print(1)\n")
        (r / "STATE.md").write_text((r / "STATE.md").read_text() + "- changed\n")
        lines, ok = sync.sync_room(r, manifest.load(r), push=False)
        self.assertTrue(any(l.startswith("room: committed") for l in lines), lines)
        status = git(["status", "--porcelain"], wsdir).stdout
        self.assertIn("?? src.py", status)
        self.assertNotIn("STATE.md", status)

    def test_kit_pinned_clone(self):
        kit_src = make_repo(Path(self.tmp.name) / "kitsrc")
        git(["tag", "v1.0.0"], kit_src)
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme")
        configure_identity(r)
        m = manifest.load(r)
        m["kits"].append({"name": "ums", "remote": str(kit_src), "ref": "v1.0.0", "path": "kits/ums"})
        manifest.save(r, m)
        lines, ok = sync.sync_ws(r, push=False)
        self.assertTrue(any("kit ums@v1.0.0: cloned" in l for l in lines), lines)
        self.assertTrue((wsdir / "kits" / "ums" / "README.md").is_file())


class TestDoctor(TempTree):
    def test_findings(self):
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme")
        configure_identity(r)
        (wsdir / "loose.txt").write_text("oops\n")
        (self.root / "stray.pdf").write_text("x")
        norem = make_repo(wsdir / "norem")
        old = time.time() - 3 * 86400
        (norem / "stale.txt").write_text("old\n")
        os.utime(norem / "stale.txt", (old, old))
        findings, warnings = doctor.run(root=self.root)
        codes = {(f.code, Path(f.path).name) for f in findings}
        self.assertIn(("LOOSE", "loose.txt"), codes)
        self.assertIn(("LOOSE", "stray.pdf"), codes)
        self.assertIn(("NOREMOTE", "norem"), codes)
        self.assertIn(("STALE", "norem"), codes)

    def test_clean_tree_passes(self):
        bare = make_bare(Path(self.tmp.name) / "remotes" / "acme-ops.git")
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme", remote=str(bare))
        configure_identity(r)
        sync.sync_ws(r)
        findings, warnings = doctor.run(root=self.root)
        errors = [f for f in findings if f.is_error]
        self.assertEqual(errors, [], [str(f) for f in errors])


class TestRegistryBootstrap(TempTree):
    def test_round_trip(self):
        remotes = Path(self.tmp.name) / "remotes"
        ops_bare = make_bare(remotes / "acme-ops.git")
        code_src = make_repo(remotes / "app-src")
        kit_src = make_repo(remotes / "kit-src")
        git(["tag", "v1.0.0"], kit_src)
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme", remote=str(ops_bare))
        configure_identity(r)
        m = manifest.load(r)
        m["repos"].append({"path": "app", "remote": str(code_src), "role": "code"})
        m["kits"].append({"name": "kit", "remote": str(kit_src), "ref": "v1.0.0", "path": "kits/kit"})
        m["servers"].append({"name": "dev", "host": "10.0.0.1", "owner": "client", "role": "dev", "access": "doppler:acme/dev/SSH"})
        manifest.save(r, m)
        (r / "STATE.md").write_text((r / "STATE.md").read_text().replace("(nothing recorded yet)", "api v1 live"))
        lines, ok = sync.sync_ws(r, push=True)
        self.assertTrue(ok, lines)
        md, js, ents = registry.write(self.root)
        self.assertTrue(md.is_file() and js.is_file())
        acme = [e for e in ents if e["name"] == "acme"][0]
        self.assertEqual(acme["room_remote"], str(ops_bare))
        self.assertIn("dev@10.0.0.1", md.read_text())

        fresh = Path(self.tmp.name) / "fresh"
        (fresh / "operation-room").mkdir(parents=True)
        (fresh / "operation-room" / "registry.json").write_text(js.read_text())
        lines, ok = bootstrap.run(fresh, only="acme")
        self.assertTrue(ok, lines)
        self.assertTrue((fresh / "clients" / "acme" / "ops" / "STATE.md").is_file())
        self.assertTrue((fresh / "clients" / "acme" / "app" / "README.md").is_file())
        self.assertTrue((fresh / "clients" / "acme" / "kits" / "kit" / "README.md").is_file())
        self.assertTrue((fresh / "clients" / "acme" / "_meta.md").is_file())
        self.assertIn("api v1 live", (fresh / "clients" / "acme" / "ops" / "STATE.md").read_text())


class TestFindRoom(TempTree):
    def test_root_falls_back_to_studio_room(self):
        hq = make_repo(self.root / "operation-room")
        r = ws.init(hq, "studio", "studio", "cwi", mode="embedded")
        self.assertEqual(room.find_room(self.root), r)
        self.assertIsNone(room.find_room(self.root / "products"))


class TestLink(TempTree):
    def test_memory_link_moves_files(self):
        wsdir = self.root / "clients" / "acme"
        r = ws.init(wsdir, "acme", "client", "acme")
        mem = self.projects / ws.enc(wsdir.resolve()) / "memory"
        mem.mkdir(parents=True)
        (mem / "feedback_one.md").write_text("lesson\n")
        done = ws.link(r, projects_dir=self.projects)
        self.assertTrue(mem.is_symlink())
        self.assertEqual(mem.resolve(), (r / "memory" / "root").resolve())
        self.assertTrue((r / "memory" / "root" / "feedback_one.md").is_file())
        done2 = ws.link(r, projects_dir=self.projects)
        self.assertEqual([d[2] for d in done2 if d[1].name == "root"], ["ok"])


if __name__ == "__main__":
    unittest.main()
