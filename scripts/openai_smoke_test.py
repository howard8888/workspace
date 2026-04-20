import os
from openai import OpenAI
import openai


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        print("OPENAI_API_KEY is missing in this shell.")
        print("Close this window, open a NEW cmd.exe, and check again.")
        return

    print(f"OPENAI_API_KEY found. Length = {len(api_key)}")

    try:
        client = OpenAI()

        response = client.responses.create(
            model="gpt-5.4",
            input="Reply with exactly: CCA8 smoke test ok."
        )

        print("\nAPI call succeeded.")
        print("Model reply:")
        print(response.output_text)

    except openai.AuthenticationError as e:
        print("\nAuthentication error.")
        print("The key may be wrong, truncated, malformed, or revoked.")
        print(e)

    except openai.RateLimitError as e:
        print("\nRate-limit / quota / billing error.")
        print(e)

    except openai.APIConnectionError as e:
        print("\nNetwork / connection error.")
        print(e)

    except openai.APIStatusError as e:
        print(f"\nAPI status error. HTTP status = {e.status_code}")
        print(e)

    except Exception as e:
        print(f"\nUnexpected error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()