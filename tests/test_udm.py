import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from helpers import FakeController, make_client

from udmlib import cli, config
from udmlib.client import APIError
from udmlib.commands import clients, firewall, guests, logs, system
from udmlib.resources import deep_merge
from udmlib.util import Brief, UsageError, load_json_arg, mac, table


def run_cli(fake: FakeController, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    env = {"UNIFI_API_KEY": "k", "UDM_HOST": "udm.test"}
    with mock.patch.dict(os.environ, env), \
            mock.patch("udmlib.client._urllib_transport", fake), \
            mock.patch("udmlib.cli.load_dotenv"), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main(list(argv))
        except SystemExit as e:  # argparse errors
            code = e.code
    return code, out.getvalue(), err.getvalue()


class ClientTests(unittest.TestCase):
    def test_unwraps_legacy_envelope(self):
        fake = FakeController().on("GET", "stat/health", [{"subsystem": "wan"}])
        self.assertEqual(make_client(fake).get(make_client(fake).legacy("stat/health")),
                         [{"subsystem": "wan"}])

    def test_api_level_error_raises(self):
        fake = FakeController().on("GET", "rest/x",
                                   {"meta": {"rc": "error", "msg": "api.err.Invalid"}},
                                   envelope=False)
        c = make_client(fake)
        with self.assertRaisesRegex(APIError, "api.err.Invalid"):
            c.get(c.legacy("rest/x"))

    def test_http_error_message_strips_html(self):
        fake = FakeController().on("GET", "x", (401, "<html><h1>401 Unauthorized</h1></html>"))
        c = make_client(fake)
        with self.assertRaises(APIError) as ctx:
            c.get(c.absolute("/x"))
        self.assertEqual(ctx.exception.status, 401)
        self.assertIn("401 Unauthorized", str(ctx.exception))
        self.assertNotIn("<h1>", str(ctx.exception))

    def test_dry_run_skips_mutations_but_not_reads(self):
        fake = FakeController().on("POST", "system-log/critical", [])
        c = make_client(fake, dry_run=True)
        res = c.post(c.legacy("cmd/stamgr"), {"cmd": "block-sta"})
        self.assertTrue(res["dry_run"])
        self.assertEqual(logs.alerts(c), [])
        self.assertEqual([m for m, _, _ in fake.calls], ["POST"])  # only the read

    def test_site_is_configurable(self):
        c = make_client(FakeController(), site="office")
        self.assertTrue(c.legacy("stat/sta").endswith("/api/s/office/stat/sta"))
        self.assertTrue(c.v2("trafficrules").endswith("/api/site/office/trafficrules"))


class UtilTests(unittest.TestCase):
    def test_mac_normalisation(self):
        self.assertEqual(mac("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(mac("aabbccddeeff"), "aa:bb:cc:dd:ee:ff")
        with self.assertRaises(Exception):
            mac("not-a-mac")

    def test_load_json_arg_from_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"a": 1}')
        try:
            self.assertEqual(load_json_arg("@" + f.name), {"a": 1})
        finally:
            os.unlink(f.name)
        with self.assertRaises(UsageError):
            load_json_arg("{nope")

    def test_deep_merge(self):
        self.assertEqual(deep_merge({"a": {"b": 1, "c": 2}, "d": 1}, {"a": {"b": 9}}),
                         {"a": {"b": 9, "c": 2}, "d": 1})

    def test_table_drops_empty_columns(self):
        out = table([{"name": "x", "empty": None}, {"name": "y", "empty": None}])
        self.assertNotIn("empty", out)
        self.assertIn("name", out)


class ConfigTests(unittest.TestCase):
    def test_dotenv_does_not_override_env(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / ".env"
            p.write_text('UDM_HOST="from-file"\nexport UDM_SITE=lab\n# comment\n')
            with mock.patch.dict(os.environ, {"UDM_HOST": "from-env"}, clear=False):
                os.environ.pop("UDM_SITE", None)
                config.load_dotenv(p)
                self.assertEqual(os.environ["UDM_HOST"], "from-env")
                self.assertEqual(os.environ["UDM_SITE"], "lab")
                os.environ.pop("UDM_SITE")

    def test_missing_key_is_a_config_error(self):
        with mock.patch.dict(os.environ, {"UNIFI_API_KEY": ""}), \
                mock.patch("udmlib.config.shutil.which", return_value=None):
            with self.assertRaises(config.ConfigError):
                config.get_api_key()


class ResourceTests(unittest.TestCase):
    def test_enable_fetches_and_puts_full_object(self):
        rule = {"_id": "r1", "name": "Block IoT", "enabled": False, "action": "drop"}
        fake = (FakeController()
                .on("GET", "rest/firewallrule", [rule])
                .on("PUT", "rest/firewallrule/r1", lambda b: [b]))
        firewall.FIREWALL_RULES.patch(make_client(fake), "r1", {"enabled": True})
        method, url, body = fake.mutations()[0]
        self.assertEqual(method, "PUT")
        self.assertEqual(body, {**rule, "enabled": True})

    def test_create_strips_ids(self):
        fake = FakeController().on("POST", "rest/portforward", lambda b: [b])
        firewall.PORT_FORWARDS.create(make_client(fake), {"_id": "x", "name": "pf"})
        self.assertEqual(fake.mutations()[0][2], {"name": "pf"})

    def test_policies_delete_uses_batch_endpoint(self):
        fake = FakeController().on("POST", "firewall-policies/batch-delete", {}, envelope=False)
        firewall.POLICIES.delete(make_client(fake), "p1")
        self.assertEqual(fake.calls[0][2], ["p1"])

    def test_v2_list_unwraps_named_key(self):
        fake = FakeController().on("GET", "firewall/zone", {"zone": [{"_id": "z"}]},
                                   envelope=False)
        self.assertEqual(firewall.ZONES.list(make_client(fake)), [{"_id": "z"}])

    def test_missing_id(self):
        fake = FakeController().on("GET", "trafficrules", [], envelope=False)
        with self.assertRaisesRegex(APIError, "no object"):
            firewall.TRAFFIC_RULES.fetch(make_client(fake), "nope")


class ClientsTests(unittest.TestCase):
    def fake(self):
        return (FakeController()
                .on("GET", "stat/sta", [{"mac": "aa:aa:aa:aa:aa:01", "hostname": "laptop",
                                         "ip": "10.0.0.5", "uptime": 10}])
                .on("GET", "stat/alluser", [
                    {"_id": "u1", "mac": "aa:aa:aa:aa:aa:01", "hostname": "laptop",
                     "network_id": "n1"},
                    {"_id": "u2", "mac": "aa:aa:aa:aa:aa:02", "name": "Printer",
                     "last_ip": "10.0.0.9"}]))

    def test_find_matches_name_and_ip(self):
        c = make_client(self.fake())
        self.assertEqual([x["_id"] for x in clients.find(c, "print")], ["u2"])
        hit = clients.find(c, "10.0.0.5")
        self.assertEqual(len(hit), 1)
        self.assertTrue(hit[0]["_online"])

    def test_merged_marks_offline(self):
        rows = {r["mac"]: r for r in clients.merged(make_client(self.fake()))}
        self.assertFalse(rows["aa:aa:aa:aa:aa:02"]["_online"])

    def test_set_fixed_ip_uses_current_network(self):
        fake = self.fake().on("PUT", "rest/user/u1", lambda b: [b])
        clients.configure(make_client(fake), "aa:aa:aa:aa:aa:01", fixed_ip="10.0.0.50")
        self.assertEqual(fake.mutations()[0][2],
                         {"use_fixedip": True, "fixed_ip": "10.0.0.50", "network_id": "n1"})

    def test_set_requires_a_change(self):
        with self.assertRaises(UsageError):
            clients.configure(make_client(self.fake()), "aa:aa:aa:aa:aa:01")


class CommandTests(unittest.TestCase):
    def test_voucher_create_returns_new_codes(self):
        fake = (FakeController()
                .on("POST", "cmd/hotspot", [{"create_time": 123}])
                .on("GET", "stat/voucher", [
                    {"_id": "v1", "code": "1234567890", "create_time": 123, "duration": 60},
                    {"_id": "v0", "code": "0000000000", "create_time": 1}]))
        res = guests.create(make_client(fake), 1, 60, 1, "guest", None, None, None)
        self.assertIsInstance(res, Brief)
        self.assertEqual([r["code"] for r in res.rows], ["12345-67890"])

    def test_summary(self):
        fake = (FakeController()
                .on("GET", "stat/health", [{"subsystem": "www", "status": "ok", "latency": 7},
                                           {"subsystem": "wan", "status": "ok",
                                            "wan_ip": "1.2.3.4"}])
                .on("GET", "stat/sysinfo", [{"version": "10.0.1"}])
                .on("GET", "stat/device", [{"name": "AP", "state": 0},
                                           {"name": "GW", "state": 1, "upgradable": True,
                                            "upgrade_to_firmware": "5.0"}])
                .on("GET", "stat/sta", [{"is_wired": True}, {"is_wired": False}])
                .on("POST", "system-log/critical", [{"id": 1}]))
        s = system.summary(make_client(fake))
        self.assertEqual(s["internet"]["wan_ip"], "1.2.3.4")
        self.assertEqual(s["devices"]["not_online"], ["AP (offline)"])
        self.assertEqual(s["devices"]["upgradable"], ["GW → 5.0"])
        self.assertEqual(s["clients"], {"online": 2, "wired": 1, "wireless": 1, "blocked": 0})
        self.assertEqual(s["unread_alerts"], 1)


    def test_vpn(self):
        from udmlib.commands import network
        fake = (FakeController()
                .on("GET", "vpn/connections", {"connections": [{"id": "s2s"}]}, envelope=False)
                .on("GET", "vpn/client-connections", {"connections": []}, envelope=False)
                .on("GET", "vpn/users", [{"name": "me"}], envelope=False))
        self.assertEqual(network.vpn(make_client(fake)),
                         {"connections": [{"id": "s2s"}], "client_connections": [],
                          "users": [{"name": "me"}]})


class CliTests(unittest.TestCase):
    def test_globals_anywhere_and_dry_run(self):
        fake = FakeController()
        code, out, _ = run_cli(fake, "clients", "--dry-run", "block", "AA:BB:CC:DD:EE:FF",
                               "--site", "lab", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertTrue(res["dry_run"])
        self.assertIn("/api/s/lab/cmd/stamgr", res["url"])
        self.assertEqual(fake.calls, [])

    def test_brief_table(self):
        fake = FakeController().on("GET", "rest/portforward", [
            {"_id": "p1", "name": "web", "enabled": True, "fwd": "10.0.0.2"}])
        code, out, _ = run_cli(fake, "portforward", "list", "--brief")
        self.assertEqual(code, 0)
        self.assertIn("web", out)
        self.assertIn("p1", out)
        code, out, _ = run_cli(fake, "pf", "--brief")
        self.assertIn("web", out)

    def test_patch_via_cli(self):
        fake = (FakeController()
                .on("GET", "trafficrules", [{"_id": "t1", "enabled": True,
                                             "description": "x"}], envelope=False)
                .on("PUT", "trafficrules/t1", (201, "{}")))
        code, _, _ = run_cli(fake, "trafficrules", "update", "t1",
                             "--patch", '{"description": "y"}')
        self.assertEqual(code, 0)
        self.assertEqual(fake.mutations()[0][2],
                         {"_id": "t1", "enabled": True, "description": "y"})

    def test_api_error_exit_code(self):
        code, _, err = run_cli(FakeController(), "routes")
        self.assertEqual(code, 1)
        self.assertIn("api.err.NotFound", err)

    def test_wlan_set_password(self):
        fake = (FakeController()
                .on("GET", "rest/wlanconf", [{"_id": "w1", "name": "Guest",
                                              "x_passphrase": "old"}])
                .on("PUT", "rest/wlanconf/w1", lambda b: [b]))
        code, _, _ = run_cli(fake, "wlans", "set-password", "w1", "new-secret")
        self.assertEqual(code, 0)
        self.assertEqual(fake.mutations()[0][2]["x_passphrase"], "new-secret")


if __name__ == "__main__":
    unittest.main()
