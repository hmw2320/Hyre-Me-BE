import os
import json
import mimetypes
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# 클라이언트 초기화
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# .env에서 모델 이름 추출 (.env에 없을 경우 기본값으로 'gemini-2.5-flash' 사용)
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

PORTFOLIO_RESPONSE_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    required=["experiences", "certifications", "languages"],
    properties={
        "experiences": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                required=["category", "title"],
                properties={
                    "category": types.Schema(type=types.Type.STRING),
                    "title": types.Schema(type=types.Type.STRING),
                    "organization": types.Schema(type=types.Type.STRING),
                    "period_text": types.Schema(type=types.Type.STRING),
                    "role": types.Schema(type=types.Type.STRING),
                    "tech_stack": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                    "achievement": types.Schema(type=types.Type.STRING),
                    "learned": types.Schema(type=types.Type.STRING),
                    "related_skills": types.Schema(type=types.Type.STRING),
                },
            ),
        ),
        "certifications": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                required=["name"],
                properties={
                    "name": types.Schema(type=types.Type.STRING),
                    "issuer": types.Schema(type=types.Type.STRING),
                    "acquired_date": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                },
            ),
        ),
        "languages": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                required=["test_name"],
                properties={
                    "test_name": types.Schema(type=types.Type.STRING),
                    "score": types.Schema(type=types.Type.STRING),
                    "grade": types.Schema(type=types.Type.STRING),
                    "acquired_date": types.Schema(type=types.Type.STRING),
                    "description": types.Schema(type=types.Type.STRING),
                },
            ),
        ),
    },
)

PORTFOLIO_SYSTEM_INSTRUCTION = """
# 지시 사항

- 첨부된 이력서, resume, 포트폴리오 파일에서 경험, 자격증, 어학 성적을 구조화된 JSON으로 추출한다.
- 출력은 반드시 한국어로 작성한다.
- 응답은 오직 JSON만 반환하고, 설명 문장, 마크다운, 코드 블록은 포함하지 않는다.
- 경험, 자격증, 어학 성적을 찾지 못하면 해당 배열은 빈 배열([])로 반환한다.
- 날짜는 가능한 경우 반드시 YYYY-MM-DD 형식 문자열로 반환하고, 알 수 없으면 생략한다. (연도만 아는 경우 YYYY, 월까지 아는 경우 YYYY-MM 형식)
- 추측으로 채우지 말고 문서에서 확인되는 정보만 사용한다.
""".strip()

PORTFOLIO_USER_PROMPT = "첨부된 파일을 분석해 포트폴리오 데이터를 추출해줘."


def _empty_portfolio_result() -> dict:
    return {"experiences": [], "certifications": [], "languages": []}


def _guess_mime_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type

    extension = os.path.splitext(file_path)[1].lower()
    fallback_mime_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".txt": "text/plain",
    }
    return fallback_mime_types.get(extension, "application/octet-stream")

def extract_portfolio_data_with_ai(file_path: str) -> dict:
    """
    저장된 이력서 파일을 구글 Gemini API에 전송하여 JSON 형태로 포트폴리오 데이터를 추출
    """
    uploaded_file = None
    try:
        # 1. 파일을 Gemini 서버에 업로드
        print(f"Uploading {file_path} to Gemini...")
        mime_type = _guess_mime_type(file_path)
        with open(file_path, "rb") as file_obj:
            uploaded_file = client.files.upload(
                file=file_obj,
                config=types.UploadFileConfig(mime_type=mime_type),
            )

        # 환경변수에서 읽어온 모델 확인용 출력
        print(f"Using AI Model: {GEMINI_MODEL_NAME}")

        # 2. 시스템 지시와 구조화 출력 스키마를 함께 적용
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[uploaded_file, PORTFOLIO_USER_PROMPT],
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=PORTFOLIO_RESPONSE_SCHEMA,
                system_instruction=[
                    types.Part.from_text(text=PORTFOLIO_SYSTEM_INSTRUCTION),
                ],
            ),
        )
        
        # 3. 응답받은 텍스트를 파이썬 딕셔너리로 변환하여 반환
        result_dict = json.loads(response.text)
        return result_dict

    except Exception as e:
        print(f"AI Extraction Error: {e}")
        # 에러 발생 시 빈 데이터 반환
        return _empty_portfolio_result()

    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as delete_error:
                print(f"Failed to delete uploaded file: {delete_error}")