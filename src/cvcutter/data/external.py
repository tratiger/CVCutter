import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

from google import genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from cvcutter.utils.exceptions import APIIntegrationError
from cvcutter.utils.logger import logger

SCOPES = [
    'https://www.googleapis.com/auth/forms.responses.readonly',
    'https://www.googleapis.com/auth/forms.body.readonly',
    'https://www.googleapis.com/auth/youtube.upload'
]

class MetadataService:
    def __init__(self, credentials_path: Path = Path("upload_metadata.json"), token_path: Path = Path("token.json")):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None

    def authenticate(self):
        """Authenticates with Google APIs."""
        if not self.credentials_path.exists():
            logger.warning(f"Credentials not found at {self.credentials_path}. Cannot use Google APIs.")
            return

        try:
            if self.token_path.exists():
                self.creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                    self.creds = flow.run_local_server(port=0)

                with open(self.token_path, 'w') as token:
                    token.write(self.creds.to_json())

            logger.info("Successfully authenticated with Google APIs.")
        except Exception as e:
            raise APIIntegrationError(f"Authentication failed: {e}")

    def get_form_responses(self, form_id: str) -> List[Dict]:
        """Fetches responses from Google Forms API."""
        if not self.creds:
            raise APIIntegrationError("Not authenticated.")

        try:
            service = build('forms', 'v1', credentials=self.creds)
            result = service.forms().responses().list(formId=form_id).execute()
            responses = result.get('responses', [])

            parsed_data = []
            for resp in responses:
                answers = resp.get('answers', {})
                row = {}
                for q_id, answer in answers.items():
                    val = answer.get('textAnswers', {}).get('answers', [{}])[0].get('value', '')
                    row[q_id] = val
                parsed_data.append(row)

            return parsed_data
        except Exception as e:
            raise APIIntegrationError(f"Failed to get form responses: {e}")

    def parse_local_csv(self, csv_path: Path) -> List[Dict]:
        """Parses a local CSV fallback for form responses."""
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            raise APIIntegrationError(f"Failed to parse CSV: {e}")

    def parse_pdf_program(self, pdf_path: Path, api_key: str) -> List[Dict]:
        """Uses Gemini to parse PDF program into structured JSON metadata."""
        logger.info(f"Parsing PDF {pdf_path} using Gemini")
        try:
            client = genai.Client(api_key=api_key)

            uploaded_file = client.files.upload(file=str(pdf_path))

            prompt = """
            Extract the concert program from this document.
            Return a JSON array of objects, where each object represents a performance.
            Keys must be exactly: "order" (integer), "title" (string), "performer" (string).
            Output ONLY valid JSON.
            """

            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=[uploaded_file, prompt]
            )

            text = response.text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.endswith("```"): text = text[:-3]

            data = json.loads(text.strip())
            return data
        except Exception as e:
            raise APIIntegrationError(f"Failed to parse PDF program: {e}")

    def map_performances(self, program_items: List[Dict], detected_segments: List[Tuple[float, float]],
                         transcripts: List[str]) -> List[Dict]:
        """
        Smart mapping: Associates PDF program items with detected video segments.
        """
        mapped = []
        for i, item in enumerate(program_items):
            start, end = detected_segments[i] if i < len(detected_segments) else (0.0, 0.0)

            mapped.append({
                "title": item.get("title", f"Performance {i+1}"),
                "performer": item.get("performer", "Unknown"),
                "start_time": start,
                "end_time": end
            })
        return mapped
