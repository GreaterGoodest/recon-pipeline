# flake8: noqa E231
import sys
import socket
import inspect
import pkgutil
import importlib
from pathlib import Path
from collections import defaultdict

import cmd2

import recon
from recon.config import tool_paths, defaults

# tool definitions for recon-pipeline's auto-installer
tools = {
    "luigi-service": {
        "installed": False,
        "dependencies": ["luigi"],
        "commands": [
            f"sudo cp {str(Path(__file__).parent.parent / 'luigid.service')} /lib/systemd/system/luigid.service",
            f"sudo cp $(which luigid) /usr/local/bin",
            "sudo systemctl daemon-reload",
            "sudo systemctl start luigid.service",
            "sudo systemctl enable luigid.service",
        ],
        "shell": True,
    },
    "luigi": {"installed": False, "dependencies": None, "commands": ["pip install luigi"]},
    "seclists": {
        "installed": False,
        "dependencies": None,
        "shell": True,
        "commands": [
            f"bash -c 'if [[ -d {defaults.get('tools-dir')}/seclists ]] ; then cd {defaults.get('tools-dir')}/seclists && git fetch --all && git pull; else git clone https://github.com/danielmiessler/SecLists.git {defaults.get('tools-dir')}/seclists; fi'"
        ],
    },
    "searchsploit": {
        "installed": False,
        "dependencies": None,
        "shell": True,
        "commands": [
            f"bash -c 'if [[ -d {Path(tool_paths.get('searchsploit')).parent} ]] ; then cd {Path(tool_paths.get('searchsploit')).parent} && git fetch --all && git pull; else git clone https://github.com/offensive-security/exploitdb.git {defaults.get('tools-dir')}/exploitdb; fi'",
            f"cp -n {Path(tool_paths.get('searchsploit')).parent}/.searchsploit_rc {Path.home().resolve()}",
            f"sed -i 's#/opt#{defaults.get('tools-dir')}#g' {Path.home().resolve()}/.searchsploit_rc",
        ],
    },
    "masscan": {
        "installed": False,
        "dependencies": None,
        "commands": [
            "git clone https://github.com/robertdavidgraham/masscan /tmp/masscan",
            "make -s -j -C /tmp/masscan",
            f"mv /tmp/masscan/bin/masscan {tool_paths.get('masscan')}",
            "rm -rf /tmp/masscan",
            f"sudo setcap CAP_NET_RAW+ep {tool_paths.get('masscan')}",
        ],
    },
    "amass": {
        "installed": False,
        "dependencies": ["go"],
        "commands": [
            f"{tool_paths.get('go')} get -u github.com/OWASP/Amass/v3/...",
            f"cp ~/go/bin/amass {tool_paths.get('amass')}",
        ],
        "shell": True,
        "environ": {"GO111MODULE": "on"},
    },
    "aquatone": {
        "installed": False,
        "dependencies": None,
        "shell": True,
        "commands": [
            "mkdir /tmp/aquatone",
            "wget -q https://github.com/michenriksen/aquatone/releases/download/v1.7.0/aquatone_linux_amd64_1.7.0.zip -O /tmp/aquatone/aquatone.zip",
            "unzip /tmp/aquatone/aquatone.zip -d /tmp/aquatone",
            f"mv /tmp/aquatone/aquatone {tool_paths.get('aquatone')}",
            "rm -rf /tmp/aquatone",
        ],
    },
    "corscanner": {
        "installed": False,
        "dependencies": None,
        "shell": True,
        "commands": [
            f"bash -c 'if [[ -d {Path(tool_paths.get('CORScanner')).parent} ]] ; then cd {Path(tool_paths.get('CORScanner')).parent} && git fetch --all && git pull; else git clone https://github.com/chenjj/CORScanner.git {Path(tool_paths.get('CORScanner')).parent}; fi'",
            f"pip install -r {Path(tool_paths.get('CORScanner')).parent / 'requirements.txt'}",
            "pip install future",
        ],
    },
    "gobuster": {
        "installed": False,
        "dependencies": ["go", "seclists"],
        "commands": [
            f"{tool_paths.get('go')} get github.com/OJ/gobuster",
            f"(cd ~/go/src/github.com/OJ/gobuster && {tool_paths.get('go')} build && {tool_paths.get('go')} install)",
        ],
        "shell": True,
    },
    "tko-subs": {
        "installed": False,
        "dependencies": ["go"],
        "commands": [
            f"{tool_paths.get('go')} get github.com/anshumanbh/tko-subs",
            f"(cd ~/go/src/github.com/anshumanbh/tko-subs && {tool_paths.get('go')} build && {tool_paths.get('go')} install)",
        ],
        "shell": True,
    },
    "subjack": {
        "installed": False,
        "dependencies": ["go"],
        "commands": [
            f"{tool_paths.get('go')} get github.com/haccer/subjack",
            f"(cd ~/go/src/github.com/haccer/subjack && {tool_paths.get('go')} install)",
        ],
        "shell": True,
    },
    "webanalyze": {
        "installed": False,
        "dependencies": ["go"],
        "commands": [
            f"{tool_paths.get('go')} get github.com/rverton/webanalyze/...",
            f"(cd ~/go/src/github.com/rverton/webanalyze && {tool_paths.get('go')} build && {tool_paths.get('go')} install)",
        ],
        "shell": True,
    },
    "recursive-gobuster": {
        "installed": False,
        "dependencies": ["gobuster", "seclists"],
        "shell": True,
        "commands": [
            f"bash -c 'if [[ -d {Path(tool_paths.get('recursive-gobuster')).parent} ]] ; then cd {Path(tool_paths.get('recursive-gobuster')).parent} && git fetch --all && git pull; else git clone https://github.com/epi052/recursive-gobuster.git {Path(tool_paths.get('recursive-gobuster')).parent}; fi'"
        ],
    },
    "go": {
        "installed": False,
        "dependencies": None,
        "commands": [
            "wget -q https://dl.google.com/go/go1.13.7.linux-amd64.tar.gz -O /tmp/go.tar.gz",
            "sudo tar -C /usr/local -xvf /tmp/go.tar.gz",
            f'bash -c \'if [[ ! $(echo "${{PATH}}" | grep $(dirname {tool_paths.get("go")})) ]]; then echo "PATH=${{PATH}}:/usr/local/go/bin" >> ~/.bashrc; fi\'',
        ],
    },
}


def get_scans():
    """ Iterates over the recon package and its modules to find all of the \*Scan classes.

    **A contract exists here that says any scans need to end with the word scan in order to be found by this function.**

    Example:
        ``defaultdict(<class 'list'>, {'AmassScan': ['recon.amass'], 'MasscanScan': ['recon.masscan'], ... })``

    Returns:
        dict containing mapping of ``classname -> [modulename, ...]`` for all potential recon-pipeline commands
    """
    scans = defaultdict(list)

    # recursively walk packages; import each module in each package
    # walk_packages yields ModuleInfo objects for all modules recursively on path
    # prefix is a string to output on the front of every module name on output.
    for loader, module_name, is_pkg in pkgutil.walk_packages(path=recon.__path__, prefix="recon."):
        importlib.import_module(module_name)

    # walk all modules, grabbing classes that we've written and add them to the classlist defaultdict
    # getmembers returns all members of an object in a list of tuples (name, value)
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.ismodule(obj) and not name.startswith("_"):
            # we're only interested in modules that don't begin with _ i.e. magic methods __len__ etc...

            for subname, subobj in inspect.getmembers(obj):
                if inspect.isclass(subobj) and subname.lower().endswith("scan"):
                    # now we only care about classes that end in [Ss]can
                    scans[subname].append(f"recon.{name}")

    return scans


# options for ReconShell's 'install' command
install_parser = cmd2.Cmd2ArgumentParser()
install_parser.add_argument("tool", help="which tool to install", choices=list(tools.keys()) + ["all"])


# options for ReconShell's 'status' command
status_parser = cmd2.Cmd2ArgumentParser()
status_parser.add_argument(
    "--port",
    help="port on which the luigi central scheduler's visualization site is running (default: 8082)",
    default="8082",
)
status_parser.add_argument(
    "--host",
    help="host on which the luigi central scheduler's visualization site is running (default: localhost)",
    default="127.0.0.1",
)


# options for ReconShell's 'scan' command
scan_parser = cmd2.Cmd2ArgumentParser()
scan_parser.add_argument("scantype", choices_function=get_scans)
scan_parser.add_argument(
    "--target-file",
    completer_method=cmd2.Cmd.path_complete,
    help="file created by the user that defines the target's scope; list of ips/domains",
)
scan_parser.add_argument(
    "--exempt-list", completer_method=cmd2.Cmd.path_complete, help="list of blacklisted ips/domains"
)
scan_parser.add_argument(
    "--results-dir", completer_method=cmd2.Cmd.path_complete, help="directory in which to save scan results"
)
scan_parser.add_argument(
    "--wordlist", completer_method=cmd2.Cmd.path_complete, help="path to wordlist used by gobuster"
)
scan_parser.add_argument(
    "--interface",
    choices_function=lambda: [x[1] for x in socket.if_nameindex()],
    help="which interface masscan should use",
)
scan_parser.add_argument("--recursive", action="store_true", help="whether or not to recursively gobust")
scan_parser.add_argument("--rate", help="rate at which masscan should scan")
scan_parser.add_argument(
    "--top-ports", help="ports to scan as specified by nmap's list of top-ports (only meaningful to around 5000)"
)
scan_parser.add_argument("--ports", help="port specification for masscan (all ports example: 1-65535,U:1-65535)")
scan_parser.add_argument("--threads", help="number of threads for all of the threaded applications to use")
scan_parser.add_argument("--scan-timeout", help="scan timeout for aquatone")
scan_parser.add_argument("--proxy", help="proxy for gobuster if desired (ex. 127.0.0.1:8080)")
scan_parser.add_argument("--extensions", help="list of extensions for gobuster (ex. asp,html,aspx)")
scan_parser.add_argument(
    "--sausage",
    action="store_true",
    help="open a web browser to Luigi's central scheduler's visualization site (see how the sausage is made!)",
)
scan_parser.add_argument(
    "--local-scheduler", action="store_true", help="use the local scheduler instead of the central scheduler (luigid)"
)
scan_parser.add_argument(
    "--verbose", action="store_true", help="shows debug messages from luigi, useful for troubleshooting"
)
