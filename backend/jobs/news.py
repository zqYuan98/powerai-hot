"""News ingest timer entrypoint."""
from jobs.ingest import main


if __name__ == "__main__":
    main(["--group", "news"])
