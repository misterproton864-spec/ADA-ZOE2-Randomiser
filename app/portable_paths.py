"""Paths for the private Windows tester distribution."""
import json, os
from pathlib import Path
APP=Path(__file__).resolve().parent
PACKAGE=APP.parent
WORK=APP/'work'
LEGACY=APP/'legacy'
HOME=Path(os.environ.get('ZOE2_BETA_HOME',str(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ADA Local23 C Test'))).resolve()
HOME.mkdir(parents=True,exist_ok=True)
CONFIG=HOME/'game.json'
BUILD_ROOT=HOME/'builds'
STATE=HOME/'state'
STATE.mkdir(exist_ok=True)
ORIGINALS=HOME/'originals'
def game():
    return Path(json.loads(CONFIG.read_text(encoding='utf-8'))['game_root']) if CONFIG.is_file() else HOME/'select-game-first'
def compiler():
    path=Path(os.environ.get('SystemRoot','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    if not path.is_file():raise FileNotFoundError('Microsoft .NET Framework 4 compiler is required. Install/enable .NET Framework 4.8, then reopen the app.')
    return str(path)
