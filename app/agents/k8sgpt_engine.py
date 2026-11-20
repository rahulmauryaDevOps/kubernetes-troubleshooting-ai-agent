import json
import subprocess


def run_k8sgpt_analysis():
    try:
        result = subprocess.run(
            [
                "k8sgpt",
                "analyze",
                "--output",
                "json"
            ],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "message": result.stderr
            }

        findings = json.loads(result.stdout)

        return {
            "status": "success",
            "findings": findings
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "K8sGPT analysis timed out"
        }

    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Invalid JSON returned by K8sGPT"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    output = run_k8sgpt_analysis()
    print(json.dumps(output, indent=4))
