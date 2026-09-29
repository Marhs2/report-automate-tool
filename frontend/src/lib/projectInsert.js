/** 새 프로젝트를 넣을 인덱스. 기준 칸이 있으면 그 바로 뒤, 없으면 끝. */
export const indexAfterCurrent = (length, preferred, current) => {
    const usable = (value) =>
        Number.isInteger(value) && value >= 0 && value < length;
    if (usable(preferred)) return preferred + 1;
    if (usable(current)) return current + 1;
    return length;
};
