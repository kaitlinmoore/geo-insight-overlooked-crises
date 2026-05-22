/**
 * mockData.ts — DEPRECATED as a data source.
 *
 * The fabricated fixtures now live server-side in `frontend/server/mock_data.py`
 * and reach the app through the FastAPI endpoints (see `lib/api.ts`). This file
 * is kept only as a backward-compatible re-export of the TypeScript contract in
 * `lib/types.ts` so existing `@/lib/mockData` imports keep working.
 *
 * New code should import types from `@/lib/types` and data from `@/lib/api`.
 */
export * from "@/lib/types";
