"""Teams Remix. Opens the app window; the app keeps running in the background to keep the theme on.
`--startup` = started by Windows at login: no window, wait for Teams, put the theme on.
`--restart` = started by the app itself right after an update: wait for the old one to be gone, then open."""
import sys
import time

import server
import teams


def main():
    startup = "--startup" in sys.argv
    teams.migrate_old_names()
    cfg = teams.load_config()
    if "--restart" in sys.argv:
        for _ in range(40):  # the old app closes a moment after starting this one
            if not server.existing_instance(cfg):
                break
            time.sleep(0.5)
        cfg = teams.load_config()
    running = server.existing_instance(cfg)
    if running:  # one instance only: just show its window
        if not startup:
            server.open_window(running)
        return
    teams.migrate_themes(server.OLD_THEMES)  # only once nobody else is running: the themes move to APPDATA
    app = server.AppServer(cfg)
    if not startup:
        server.open_window(app.url)
    app.serve(startup=startup)


if __name__ == "__main__":
    main()
