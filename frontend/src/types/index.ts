export interface Insight {
  research_question_id: string;
  research_question_label: string;
  finding: string;
  evidence: { quote: string; source_chunk: string }[];
  implication: string;
  segment: string;
  confidence: number;
  chunk_ids: string[];
  metadata_filter_applied?: Record<string, unknown>;
  evidence_linked?: { quote: string; grounded: boolean; source_chunk_id: string }[];
  faithfulness_score?: number;
  faithfulness_passed?: boolean;
  faithfulness_judge?: string;
}

export interface Theme {
  cluster_id: number;
  theme_name: string;
  category: string;
  barrier: string;
  description: string;
  quotes: string[];
  keywords?: string[];
  representative_chunks?: string[];
  num_samples?: number;
}

export interface Segment {
  segment: string;
  insights: {
    research_question_id: string;
    research_question_label: string;
    finding: string;
    implication: string;
    confidence: number;
  }[];
  research_questions: string[];
  average_confidence: number;
  evidence_count: number;
  insight_count: number;
}

export interface Review {
  source: string;
  app: string;
  text: string;
  rating: number;
  date: string;
  language: string;
}

export interface ReviewFilters {
  sources: string[];
  apps: string[];
  ratings: number[];
}

export interface Distribution {
  by_source: Record<string, number>;
  by_app: Record<string, number>;
  by_rating: Record<string, number>;
}

export interface EvalReport {
  pipeline_run_timestamp: string;
  phase: string;
  passed: boolean;
  faithfulness: {
    total_insights: number;
    passed: number;
    failed: number;
    average_score: number;
    per_insight: Record<string, {
      research_question_id: string;
      faithfulness_score: number;
      faithfulness_passed: boolean;
      judge: string;
      reasoning: string;
    }>;
  };
  coverage: {
    all_questions_covered: boolean;
    coverage_count: number;
    total_questions: number;
    missing_questions: string[];
  };
  contradictions: {
    unresolved: Array<{
      insight_a: string;
      insight_b: string;
      finding_a: string;
      finding_b: string;
      contradicts: boolean;
      severity: string;
    }>;
  };
  spot_check: {
    total_reviews: number;
    hallucinated_count: number;
    grounded_count: number;
    partially_grounded_count: number;
  };
}

export interface Stats {
  phase: string;
  raw_records: number;
  clean_chunks: number;
  sources: string[];
  apps: string[];
  date_range: { earliest: string | null; latest: string | null };
  total_insights: number;
  total_themes: number;
  eval_passed: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  count: number;
  total: number;
  page: number;
  page_size: number;
}
