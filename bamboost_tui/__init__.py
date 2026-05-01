from bamboost_tui.utils import get_index as get_index


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        default=None,
        nargs="?",
    )
    from .app import BamboostApp

    args = parser.parse_args()

    app = BamboostApp(
        watch_css=True, initial_collection_path=args.path
    )
    res = app.run()

    if res:
        import sys

        sys.stdout.write(res)
        sys.stdout.flush()
