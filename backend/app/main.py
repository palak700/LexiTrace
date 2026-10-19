from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.auth import router as auth_router
from app.core.config import settings

app = FastAPI(title='LexiTrace API', description='Document-level AI text detection API', version='0.2.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, 'http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_credentials=True, allow_methods=['*'], allow_headers=['*'],
)
app.include_router(router, prefix='/api')
app.include_router(auth_router, prefix='/api')
app.include_router(router)
