export interface AgricultureFields { crop?: string; variety?: string; stage?: string; issue?: string; environment?: string; attempted?: string; observation?: string; references?: string[] }
export interface ContentAsset { id: number; filename: string; media_type: string }
export interface ForumComment { id: number; author: string; body: string; parent_id: number | null; created_at: string; can_delete: boolean }
export interface ForumPost {
  id: number; title: string; body: string; category: string; visibility: string; status: string; review_state: string
  fields: AgricultureFields; tags: string[]; author: string; author_id: number; version: number; created_at: string; updated_at: string
  accepted_comment_id: number | null; can_edit: boolean; can_moderate: boolean
  likes: number; liked: boolean; bookmarked: boolean; comment_count: number; comments?: ForumComment[]; assets?: ContentAsset[]
}
export interface PostInput { title: string; body: string; category: string; visibility: string; fields?: AgricultureFields; tags?: string[]; asset_ids?: number[]; version?: number; research_source_id?: number; publish_confirmed?: boolean }
export interface Page<T> { items: T[]; total: number; page: number; page_size?: number }
export interface Reference { category?:string;stages?:string[];topics?:string[];updated_at?:string;language?:string;id: string; title: string; summary: string; guidance?: string[]; sources: { name: string; url?: string; document_id?: number; chunk_id?: number; position?: string }[]; position?: string; source_quality?: string; applicability?: string; crops?: string[] }
export interface ForumAnalysis { analysis: string; sources: Reference[]; mode: string; published: boolean; notice: string }
export interface ForumReport { id: number; post_id: number; title: string; reason: string; status: string; resolution: string | null }
export interface NewsSource { id: number; name: string; url: string; kind: string; enabled: boolean; permission_note: string; failures: number; last_error: string | null; last_checked_at: string | null; next_retry_at: string | null }
export interface NewsArticle { source_id?: number; id: number; title: string; source: string; url: string; published_at: string | null; collected_at: string; summary: string; tags: string[]; status: string; analysis: { headline?:string;key_points?:string[];evidence_kind?:string;auto_status?:string;method?: string; link_status?: string; link_checked_at?: string; crops?: string[]; stages?: string[]; concerns?: string[]; relevance_reason?: string; uncertainty?: string }; bookmarked: boolean; read_at: string | null }
export interface NewsPreference { crops: string[]; topics: string[]; enabled: boolean; local_hour: number }
export interface NewsDigest { id: number; day: string; body: string; read_at: string | null; created_at: string; articles: NewsArticle[] }
export interface Job { key: string; status: string; attempts: number; updated_at: string; result: { added?: number; error?: string } }
export interface KnowledgeDocument { can_delete?: boolean; id: number; title: string; filename: string; source_url: string | null; source_quality: string; crops: string[]; stages: string[]; applicability: string; status: string; parser: string; error: string | null; created_at: string; updated_at: string; chunk_count: number; chunks?: { id: number; position: string; content: string }[] }
export interface Evaluation { id: number; suite_version: string; model_version: string; mode: string; passed: number; total: number; created_at: string; note: string; results: { case: string; passed: boolean; elapsed_ms: number; evidence?: Record<string, unknown>; error_code?: string }[] }
export interface TraceSummary { items: { id: number; run_id: number; operation: string; status: string; elapsed_ms: number; error_code: string | null; usage: Record<string, number>; created_at: string }[]; tool_calls: number; tool_success_rate: number | null; token_total: number; actual_cost: number | null; cost_note: string; window_note: string }
