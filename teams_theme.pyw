"""Teams Remix. Opens the app window; the app keeps running in the background to keep the theme on.
`--startup` = started by Windows at login: no window, wait for Teams, put the theme on."""
import sys

import server
import teams


def main():
    startup = "--startup" in sys.argv
    teams.migrate_old_names()
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
