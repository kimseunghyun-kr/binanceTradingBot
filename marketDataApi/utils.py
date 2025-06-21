import logging
import requests
import time
from typing import Optional
from requests.exceptions import ConnectTimeout, ReadTimeout, RequestException

###############################################################################
# HELPER: EXPONENTIAL RETRY WRAPPER
###############################################################################
def retry_request(
    url: str,
    method: str = "GET",
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout: int = 20,
    max_retries: int = 5
):
    attempt = 0
    while attempt < max_retries:
        try:
            if method.upper() == "GET":
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            else:
                resp = requests.post(url, data=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (ConnectTimeout, ReadTimeout, RequestException) as e:
            logging.error(f"Request error on attempt {attempt+1} for {url}: {e}")
            time.sleep(2 ** attempt)
            attempt += 1
    logging.error(f"Max retries ({max_retries}) reached for {url}.")
    return None
