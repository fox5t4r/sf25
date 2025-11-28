#!/bin/bash
UPLOAD_BASE_DIR="/app/uploads"
MAX_FILE_AGE_MINUTES=120 
LOG_PREFIX="[CLEANUP]"

echo "${LOG_PREFIX} 정리 작업 시작: $(date '+%Y-%m-%d %H:%M:%S')"

if [ ! -d "${UPLOAD_BASE_DIR}" ]; then
    echo "${LOG_PREFIX} 업로드 디렉토리가 없습니다: ${UPLOAD_BASE_DIR}"
    exit 1
fi

deleted_files=0
deleted_dirs=0

for user_dir in "${UPLOAD_BASE_DIR}"/*; do
    [ ! -d "${user_dir}" ] && continue
    
    session_id=$(basename "${user_dir}")
    has_files=false
    
    echo "${LOG_PREFIX} 세션 검사: ${session_id}"

    find "${user_dir}" -type f | while read -r file_path; do
        file_age_minutes=$(( ($(date +%s) - $(stat -c %Y "${file_path}")) / 60 ))
        
        if [ ${file_age_minutes} -gt ${MAX_FILE_AGE_MINUTES} ]; then
            echo "${LOG_PREFIX} 삭제: ${file_path} (${file_age_minutes}분 경과)"
            rm -f "${file_path}"
            deleted_files=$((deleted_files + 1))
        else
            has_files=true
        fi
    done

    if [ -z "$(ls -A ${user_dir})" ]; then
        echo "${LOG_PREFIX} 빈 디렉토리 삭제: ${user_dir}"
        rmdir "${user_dir}"
        deleted_dirs=$((deleted_dirs + 1))
    fi
done

echo "${LOG_PREFIX} 추가 정리 대상 검사..."

if [ -d "/tmp" ]; then
    find /tmp -type f -name "sess_*" -mmin +${MAX_FILE_AGE_MINUTES} -delete 2>/dev/null
    echo "${LOG_PREFIX} 임시 세션 파일 정리 완료"
fi

if [ -d "/app/__pycache__" ]; then
    find /app/__pycache__ -type f -mmin +${MAX_FILE_AGE_MINUTES} -delete 2>/dev/null
    echo "${LOG_PREFIX} Python 캐시 정리 완료"
fi

find /app -type f -name "*.pyc" -mmin +${MAX_FILE_AGE_MINUTES} -delete 2>/dev/null

if [ -f "/app/upload.log" ]; then
    log_size=$(stat -c %s "/app/upload.log" 2>/dev/null || echo 0)
    if [ ${log_size} -gt 10485760 ]; then  # 10MB
        echo "${LOG_PREFIX} 로그 파일 크기 초과, 백업 및 초기화"
        gzip -c /app/upload.log > /app/upload.log.$(date +%Y%m%d%H%M%S).gz
        > /app/upload.log
    fi
fi

echo "${LOG_PREFIX} 정리 완료: 파일 ${deleted_files}개, 디렉토리 ${deleted_dirs}개 삭제"
echo "${LOG_PREFIX} 종료: $(date '+%Y-%m-%d %H:%M:%S')"
