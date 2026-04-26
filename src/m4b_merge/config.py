from pathlib import Path
import shutil
from appdirs import user_config_dir

# config section for docker
if Path('/config').is_dir():
    config_path = Path('/config')
else:
    appname = "m4b-merge"
    config_path = Path(user_config_dir(appname))
    Path(config_path).mkdir(
        parents=True,
        exist_ok=True
    )

# Discover external binaries lazily; consumers check at use-time.
# Patch 5 replaces this module with runtime_config.discover() that fails
# fast when binaries are missing.
m4b_tool_bin = shutil.which('m4b-tool')
mp4chaps_bin = shutil.which('mp4chaps')
