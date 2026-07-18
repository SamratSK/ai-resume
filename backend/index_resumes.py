"""One-time resume indexing command: python -m backend.index_resumes."""
from __future__ import annotations

from backend import state


def main() -> None:
    state.init_singletons()
    try:
        result = state.chat_service.index_all()
        print(f"Indexed {len(result)} resumes; {sum(max(count, 0) for count in result.values())} chunks changed.")
        failed = [doc_id for doc_id, count in result.items() if count < 0]
        if failed:
            print(f"Failed: {', '.join(failed)}")
    finally:
        state.shutdown_singletons()


if __name__ == "__main__":
    main()
