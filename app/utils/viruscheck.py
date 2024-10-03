import base64
import logging

import vt
from pydantic import BaseModel


class VirusTotalResults(BaseModel):
    md5: str
    sha256: str
    url: str
    is_safe: bool


class VirusCheck:
    def __init__(self, vt_api_key: str):
        self.api_key = vt_api_key
        self.logger = logging.getLogger(__name__)

    async def check_file(self, file_path: str) -> VirusTotalResults:
        """Upload and scan a file with VirusTotal"""
        async with vt.Client(self.api_key) as client:
            with open(file_path, "rb") as f:
                self.logger.info(f"Uploading {file_path}")
                analysis = await client.scan_file_async(f)
                self.logger.info(f"File {file_path} uploaded.")

                completed_analysis = await client.wait_for_analysis_completion(analysis)

                self.logger.info(f"{file_path}: {completed_analysis.stats}")

                # TODO probably a better way to obtain the sha256
                decoded = base64.b64decode(analysis.id).decode("utf-8")
                md5 = decoded.split(":")[0]
                file_details = await client.get_object_async("/files/" + md5)

                url = "https://www.virustotal.com/gui/file/" + file_details.sha256
                is_safe = completed_analysis.stats["malicious"] == 0

                return VirusTotalResults(
                    md5=md5, sha256=file_details.sha256, url=url, is_safe=is_safe
                )
