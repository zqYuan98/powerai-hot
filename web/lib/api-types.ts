// 自动生成，请勿手改：npm run gen:api
export interface paths {
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Items */
        get: operations["list_items_api_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search
         * @description 访客按 IP 限频：每次搜索都要调向量与重排模型。
         */
        get: operations["search_api_items_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/by-ids": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Items By Ids
         * @description 按给定顺序取卡片（访客存在本机的收藏）；不存在或未完成精读的静默跳过。
         */
        get: operations["items_by_ids_api_items_by_ids_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Item */
        get: operations["get_item_api_items__item_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Item */
        patch: operations["patch_item_api_items__item_id__patch"];
        trace?: never;
    };
    "/api/leads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Leads */
        get: operations["list_leads_api_leads_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/leads/provinces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Lead Provinces */
        get: operations["lead_provinces_api_leads_provinces_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/hot": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Hot */
        get: operations["hot_api_hot_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stories/{story_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Story Detail */
        get: operations["story_detail_api_stories__story_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/digests": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Digests */
        get: operations["list_digests_api_digests_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/digests/{kind}/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Latest Digest */
        get: operations["latest_digest_api_digests__kind__latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/digests/{kind}/{period_start}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Digest */
        get: operations["get_digest_api_digests__kind___period_start__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Knowledge */
        get: operations["list_knowledge_api_knowledge_get"];
        put?: never;
        /**
         * Submit Knowledge
         * @description 粘贴链接收录；抓不到正文（公众号风控、纯图片）时可以连同正文一起提交。
         */
        post: operations["submit_knowledge_api_knowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/facets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Knowledge Facets */
        get: operations["knowledge_facets_api_knowledge_facets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/related": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Related To Item
         * @description 与一条资讯/商机语义相近的知识（没配置 Embedding 或没有足够接近的就返回空）。
         */
        get: operations["related_to_item_api_knowledge_related_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/{article_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Knowledge */
        get: operations["get_knowledge_api_knowledge__article_id__get"];
        put?: never;
        post?: never;
        /** Delete Knowledge */
        delete: operations["delete_knowledge_api_knowledge__article_id__delete"];
        options?: never;
        head?: never;
        /** Patch Knowledge */
        patch: operations["patch_knowledge_api_knowledge__article_id__patch"];
        trace?: never;
    };
    "/api/meta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Meta */
        get: operations["meta_api_meta_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/site/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Feedback */
        post: operations["submit_feedback_api_site_feedback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 最近的精选或全部动态 */
        get: operations["v1_items_api_v1_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 按关键词与语义搜索全部已精读条目 */
        get: operations["v1_search_api_v1_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/leads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 结构化商机（招标、中标、项目、规划） */
        get: operations["v1_leads_api_v1_leads_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/hot": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 当前热点事件（按独立信源数与时间衰减排序） */
        get: operations["v1_hot_stories_api_v1_hot_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 一个事件的时间线与 AI 综述 */
        get: operations["v1_story_detail_api_v1_stories__story_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/knowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 电力基建知识库：公众号与专业网站文章的知识卡片 */
        get: operations["v1_knowledge_list_api_v1_knowledge_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dailies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 日报 / 周报目录 */
        get: operations["v1_dailies_api_v1_dailies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dailies/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 最新一期日报 / 周报 */
        get: operations["v1_daily_latest_api_v1_dailies_latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dailies/{day}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** 指定日期的日报 / 周报 */
        get: operations["v1_daily_api_v1_dailies__day__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/leads/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Lead */
        patch: operations["patch_lead_api_leads__item_id__patch"];
        trace?: never;
    };
    "/api/digests/{kind}/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate */
        post: operations["generate_api_digests__kind__generate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/knowledge/{article_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry Knowledge */
        post: operations["retry_knowledge_api_knowledge__article_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/feedback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Feedback */
        get: operations["list_feedback_api_feedback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/feedback/{feedback_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Feedback */
        patch: operations["patch_feedback_api_feedback__feedback_id__patch"];
        trace?: never;
    };
    "/api/gold/stats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Gold Stats */
        get: operations["gold_stats_api_gold_stats_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gold/next": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Gold Next */
        get: operations["gold_next_api_gold_next_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/gold/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Gold Case */
        get: operations["gold_case_api_gold__item_id__get"];
        /** Put Label */
        put: operations["put_label_api_gold__item_id__put"];
        post?: never;
        /** Delete Label */
        delete: operations["delete_label_api_gold__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/eval-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_api_eval_runs_get"];
        put?: never;
        /** Start Run */
        post: operations["start_run_api_eval_runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/eval-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_eval_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sources */
        get: operations["list_sources_api_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sources/{source_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Source */
        patch: operations["patch_source_api_sources__source_id__patch"];
        trace?: never;
    };
    "/api/sources/{source_id}/collect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Collect Now */
        post: operations["collect_now_api_sources__source_id__collect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sources/{source_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Source Runs */
        get: operations["source_runs_api_sources__source_id__runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/watch-rules": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Rules */
        get: operations["list_rules_api_watch_rules_get"];
        put?: never;
        /** Create Rule */
        post: operations["create_rule_api_watch_rules_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/watch-rules/{rule_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Rule */
        put: operations["update_rule_api_watch_rules__rule_id__put"];
        post?: never;
        /** Delete Rule */
        delete: operations["delete_rule_api_watch_rules__rule_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tuning": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Tuning */
        get: operations["get_tuning_api_tuning_get"];
        /** Put Tuning */
        put: operations["put_tuning_api_tuning_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Usage */
        get: operations["usage_api_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pipeline": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Pipeline Stats */
        get: operations["pipeline_stats_api_pipeline_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Jobs */
        get: operations["list_jobs_api_jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/retry-failed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Retry Failed Items
         * @description 修好模型配置后，一键重试所有失败条目（包括配置类故障挂起的）。
         */
        post: operations["retry_failed_items_api_items_retry_failed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ArticleStatus
         * @enum {string}
         */
        ArticleStatus: "new" | "analyzed" | "rejected" | "duplicate" | "hidden" | "failed";
        /**
         * BizLine
         * @enum {string}
         */
        BizLine: "inspection_ai" | "grid_epc" | "other";
        /**
         * Channel
         * @enum {string}
         */
        Channel: "tender" | "award" | "project" | "planning" | "policy" | "market" | "company" | "tech" | "industry";
        /** ChannelCount */
        ChannelCount: {
            channel: components["schemas"]["Channel"];
            /** Label */
            label: string;
            /** Today */
            today: number;
        };
        /** DigestBrief */
        DigestBrief: {
            /** Id */
            id: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "daily" | "weekly";
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /** Issue No */
            issue_no: number;
            /** Title */
            title: string;
            /** Lead Title */
            lead_title: string | null;
            /**
             * Item Count
             * @default 0
             */
            item_count: number;
        };
        /** DigestDetail */
        DigestDetail: {
            /** Id */
            id: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "daily" | "weekly";
            /**
             * Period Start
             * Format: date
             */
            period_start: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /** Issue No */
            issue_no: number;
            /** Title */
            title: string;
            /** Lead Title */
            lead_title: string | null;
            /**
             * Item Count
             * @default 0
             */
            item_count: number;
            /** Overview */
            overview: string | null;
            lead: components["schemas"]["ItemCard"] | null;
            /** Sections */
            sections: components["schemas"]["DigestSection"][];
            /** Stats */
            stats: {
                [key: string]: number;
            };
            /** Markdown */
            markdown: string;
        };
        /**
         * DigestKind
         * @enum {string}
         */
        DigestKind: "daily" | "weekly";
        /** DigestSection */
        DigestSection: {
            /** Name */
            name: string;
            /** Comment */
            comment: string;
            /** Items */
            items: components["schemas"]["ItemCard"][];
        };
        /** DimWeights */
        DimWeights: {
            /**
             * Relevance
             * @default 0.3
             */
            relevance: number;
            /**
             * Opportunity
             * @default 0.3
             */
            opportunity: number;
            /**
             * Certainty
             * @default 0.15
             */
            certainty: number;
            /**
             * Timeliness
             * @default 0.1
             */
            timeliness: number;
            /**
             * Impact
             * @default 0.15
             */
            impact: number;
        };
        /** Dims */
        Dims: {
            /** Relevance */
            relevance: number | null;
            /** Opportunity */
            opportunity: number | null;
            /** Certainty */
            certainty: number | null;
            /** Timeliness */
            timeliness: number | null;
            /** Impact */
            impact: number | null;
        };
        /** EvalRunBrief */
        EvalRunBrief: {
            /** Id */
            id: number;
            /** Label */
            label: string;
            /** Mode */
            mode: string;
            /** Split */
            split: string;
            /** Status */
            status: string;
            /** Error */
            error: string | null;
            /** Metrics */
            metrics: {
                [key: string]: unknown;
            };
            /** Cost Yuan */
            cost_yuan: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Finished At */
            finished_at: string | null;
        };
        /** EvalRunDetail */
        EvalRunDetail: {
            /** Id */
            id: number;
            /** Label */
            label: string;
            /** Mode */
            mode: string;
            /** Split */
            split: string;
            /** Status */
            status: string;
            /** Error */
            error: string | null;
            /** Metrics */
            metrics: {
                [key: string]: unknown;
            };
            /** Cost Yuan */
            cost_yuan: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Finished At */
            finished_at: string | null;
            /** Params */
            params: {
                [key: string]: unknown;
            };
            /** Sweep */
            sweep: {
                [key: string]: unknown;
            }[];
            /** Errors */
            errors: {
                [key: string]: unknown;
            }[];
        };
        /** EvalRunIn */
        EvalRunIn: {
            /**
             * Mode
             * @default stored
             * @enum {string}
             */
            mode: "stored" | "rerun";
            /**
             * Split
             * @default development
             * @enum {string}
             */
            split: "development" | "holdout" | "all";
            /** Label */
            label?: string | null;
        };
        /** FacetCount */
        FacetCount: {
            /** Key */
            key: string;
            /** Label */
            label: string;
            /** Count */
            count: number;
        };
        /** FeedbackAck */
        FeedbackAck: {
            /** Id */
            id: number;
        };
        /** FeedbackIn */
        FeedbackIn: {
            /** Content */
            content: string;
            /** Contact */
            contact?: string | null;
            /** Page Url */
            page_url?: string | null;
        };
        /** FeedbackOut */
        FeedbackOut: {
            /** Id */
            id: number;
            /** Content */
            content: string;
            /** Contact */
            contact: string | null;
            /** Page Url */
            page_url: string | null;
            /** Ip */
            ip: string | null;
            /** User Agent */
            user_agent: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "new" | "done";
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
        };
        /** FeedbackPatch */
        FeedbackPatch: {
            /**
             * Status
             * @enum {string}
             */
            status: "new" | "done";
        };
        /**
         * FollowStatus
         * @enum {string}
         */
        FollowStatus: "new" | "watching" | "following" | "ignored" | "closed";
        /**
         * GoldCase
         * @description 待标注条目：只给原文，不给分数、AI 摘要和精选结论，避免标注被系统判断带偏。
         */
        GoldCase: {
            /** Item Id */
            item_id: number;
            /** Title */
            title: string;
            /** Url */
            url: string;
            /** Source Name */
            source_name: string;
            /** Tier */
            tier: string;
            /** Published At */
            published_at: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /** Body */
            body: string | null;
            /** Decision */
            decision: ("select" | "reject" | "either") | null;
            /** Note */
            note: string | null;
        };
        /** GoldLabelIn */
        GoldLabelIn: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "select" | "reject" | "either";
            /** Note */
            note?: string | null;
        };
        /** GoldRecent */
        GoldRecent: {
            /** Item Id */
            item_id: number;
            /** Title */
            title: string;
            /**
             * Decision
             * @enum {string}
             */
            decision: "select" | "reject" | "either";
            /**
             * Labeled At
             * Format: date-time
             */
            labeled_at: string;
        };
        /** GoldStats */
        GoldStats: {
            /** Total */
            total: number;
            /** Target */
            target: number;
            /** Decision */
            decision: {
                [key: string]: number;
            };
            /** Stratum */
            stratum: {
                [key: string]: number;
            };
            /** Split */
            split: {
                [key: string]: number;
            };
            /** Recent */
            recent: components["schemas"]["GoldRecent"][];
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HotStory */
        HotStory: {
            /** Rank */
            rank: number;
            story: components["schemas"]["StoryBrief"];
            lead_item: components["schemas"]["ItemCard"];
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** Is New */
            is_new: boolean;
        };
        /** ItemCard */
        ItemCard: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Title Zh */
            title_zh: string | null;
            /** Url */
            url: string;
            source: components["schemas"]["SourceBrief"];
            /** Tier */
            tier: string;
            channel: components["schemas"]["Channel"];
            /** Province */
            province: string | null;
            /** Summary */
            summary: string | null;
            /** Reason */
            reason: string | null;
            /** Action */
            action: string | null;
            /** Tags */
            tags: string[];
            /** Score */
            score: number | null;
            /** Selected */
            selected: boolean;
            /** Published At */
            published_at: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /** Story Id */
            story_id: number | null;
            /**
             * Also Reported
             * @default 0
             */
            also_reported: number;
            /**
             * Starred
             * @default false
             */
            starred: boolean;
            /**
             * Read
             * @default false
             */
            read: boolean;
            lead: components["schemas"]["LeadOut"] | null;
        };
        /** ItemDetail */
        ItemDetail: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Title Zh */
            title_zh: string | null;
            /** Url */
            url: string;
            source: components["schemas"]["SourceBrief"];
            /** Tier */
            tier: string;
            channel: components["schemas"]["Channel"];
            /** Province */
            province: string | null;
            /** Summary */
            summary: string | null;
            /** Reason */
            reason: string | null;
            /** Action */
            action: string | null;
            /** Tags */
            tags: string[];
            /** Score */
            score: number | null;
            /** Selected */
            selected: boolean;
            /** Published At */
            published_at: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /** Story Id */
            story_id: number | null;
            /**
             * Also Reported
             * @default 0
             */
            also_reported: number;
            /**
             * Starred
             * @default false
             */
            starred: boolean;
            /**
             * Read
             * @default false
             */
            read: boolean;
            lead: components["schemas"]["LeadOut"] | null;
            /** Content Html */
            content_html: string | null;
            /** Content Text */
            content_text: string | null;
            /** Note */
            note: string | null;
            /** Status */
            status: string;
            /** Status Reason */
            status_reason: string | null;
            dims: components["schemas"]["Dims"];
            story: components["schemas"]["StoryBrief"] | null;
            /** Related */
            related: components["schemas"]["ItemCard"][];
        };
        /** ItemPatch */
        ItemPatch: {
            /** Starred */
            starred?: boolean | null;
            /** Read */
            read?: boolean | null;
            /** Note */
            note?: string | null;
        };
        /** JobOut */
        JobOut: {
            /** Id */
            id: number;
            /** Kind */
            kind: string;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /** Status */
            status: string;
            /** Attempts */
            attempts: number;
            /** Error */
            error: string | null;
            /** Result */
            result: {
                [key: string]: unknown;
            } | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Finished At */
            finished_at: string | null;
        };
        /**
         * JobStatus
         * @enum {string}
         */
        JobStatus: "queued" | "running" | "done" | "failed";
        /** KnowledgeCard */
        KnowledgeCard: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Original Title */
            original_title: string;
            /** Url */
            url: string;
            /** Account */
            account: string | null;
            /** Published At */
            published_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            domain: components["schemas"]["KnowledgeDomain"];
            ktype: components["schemas"]["KnowledgeType"];
            /** Tags */
            tags: string[];
            /** Summary */
            summary: string | null;
            /** Key Points */
            key_points: string[];
            /** Scenarios */
            scenarios: string | null;
            /** Solution Use */
            solution_use: string | null;
            /** Standards */
            standards: string[];
            /** Score */
            score: number | null;
            /** Featured */
            featured: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "new" | "analyzed" | "rejected" | "duplicate" | "hidden" | "failed";
            /** Status Reason */
            status_reason: string | null;
        };
        /** KnowledgeDetail */
        KnowledgeDetail: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Original Title */
            original_title: string;
            /** Url */
            url: string;
            /** Account */
            account: string | null;
            /** Published At */
            published_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            domain: components["schemas"]["KnowledgeDomain"];
            ktype: components["schemas"]["KnowledgeType"];
            /** Tags */
            tags: string[];
            /** Summary */
            summary: string | null;
            /** Key Points */
            key_points: string[];
            /** Scenarios */
            scenarios: string | null;
            /** Solution Use */
            solution_use: string | null;
            /** Standards */
            standards: string[];
            /** Score */
            score: number | null;
            /** Featured */
            featured: boolean;
            /**
             * Status
             * @enum {string}
             */
            status: "new" | "analyzed" | "rejected" | "duplicate" | "hidden" | "failed";
            /** Status Reason */
            status_reason: string | null;
            dims: components["schemas"]["KnowledgeDims"];
            /** Related */
            related: components["schemas"]["KnowledgeCard"][];
            /** Content Text */
            content_text: string | null;
            /** Note */
            note: string | null;
            /** Duplicate Of */
            duplicate_of: number | null;
        };
        /** KnowledgeDims */
        KnowledgeDims: {
            /** Depth */
            depth: number | null;
            /** Practical */
            practical: number | null;
            /** Accuracy */
            accuracy: number | null;
            /** Originality */
            originality: number | null;
        };
        /**
         * KnowledgeDomain
         * @enum {string}
         */
        KnowledgeDomain: "transmission" | "substation" | "distribution" | "civil" | "commissioning" | "inspection" | "renewable" | "general";
        /** KnowledgeFacets */
        KnowledgeFacets: {
            /** Total */
            total: number;
            /** Domains */
            domains: components["schemas"]["FacetCount"][];
            /** Types */
            types: components["schemas"]["FacetCount"][];
            /** Status */
            status: {
                [key: string]: number;
            };
        };
        /** KnowledgePage */
        KnowledgePage: {
            /** Items */
            items: components["schemas"]["KnowledgeCard"][];
            /** Total */
            total: number;
        };
        /** KnowledgePatch */
        KnowledgePatch: {
            /** Note */
            note?: string | null;
            /** Hidden */
            hidden?: boolean | null;
            domain?: components["schemas"]["KnowledgeDomain"] | null;
            ktype?: components["schemas"]["KnowledgeType"] | null;
        };
        /** KnowledgeSubmit */
        KnowledgeSubmit: {
            /** Url */
            url: string;
            /** Title */
            title?: string | null;
            /**
             * Content
             * @description 抓不到正文时直接粘贴
             */
            content?: string | null;
            /** Note */
            note?: string | null;
        };
        /** KnowledgeSubmitAck */
        KnowledgeSubmitAck: {
            /** Id */
            id: number;
            /** Existed */
            existed: boolean;
            /** Status */
            status: string;
        };
        /**
         * KnowledgeType
         * @enum {string}
         */
        KnowledgeType: "principle" | "construction" | "standard" | "design" | "safety" | "cost" | "bidding" | "management" | "tech";
        /** LeadOut */
        LeadOut: {
            /** Project Name */
            project_name: string | null;
            /** Owner */
            owner: string | null;
            /** Province */
            province: string | null;
            /** Voltage Kv */
            voltage_kv: number | null;
            /** Amount Wan */
            amount_wan: string | null;
            stage: components["schemas"]["Stage"];
            /** Bid No */
            bid_no: string | null;
            /** Deadline At */
            deadline_at: string | null;
            /** Qualification */
            qualification: string | null;
            /** Winner */
            winner: string | null;
            biz_line: components["schemas"]["BizLine"];
            /** Match Score */
            match_score: number;
            /** Dropped Fields */
            dropped_fields: string[];
            follow_status: components["schemas"]["FollowStatus"];
            /** Follow Note */
            follow_note: string | null;
            /** Remind At */
            remind_at: string | null;
        };
        /** LeadPage */
        LeadPage: {
            /** Items */
            items: components["schemas"]["LeadRow"][];
            /** Total */
            total: number;
        };
        /** LeadPatch */
        LeadPatch: {
            follow_status?: components["schemas"]["FollowStatus"] | null;
            /** Follow Note */
            follow_note?: string | null;
            /** Remind At */
            remind_at?: string | null;
        };
        /** LeadRow */
        LeadRow: {
            item: components["schemas"]["ItemCard"];
            lead: components["schemas"]["LeadOut"];
        };
        /** LoginIn */
        LoginIn: {
            /** Password */
            password: string;
        };
        /** Meta */
        Meta: {
            /** Channels */
            channels: components["schemas"]["ChannelCount"][];
            /** Last Collect At */
            last_collect_at: string | null;
            /** Sources Enabled */
            sources_enabled: number;
            /** Llm Enabled */
            llm_enabled: boolean;
            /** Embedding Enabled */
            embedding_enabled: boolean;
            /** Push Enabled */
            push_enabled: boolean;
            /** Auth Required */
            auth_required: boolean;
        };
        /** Ok */
        Ok: {
            /**
             * Ok
             * @default true
             */
            ok: boolean;
            /** Detail */
            detail: string | null;
        };
        /** Page[ItemCard] */
        Page_ItemCard_: {
            /** Items */
            items: components["schemas"]["ItemCard"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** PipelineStats */
        PipelineStats: {
            /** Items 24H */
            items_24h: number;
            /** Analyzed 24H */
            analyzed_24h: number;
            /** Selected 24H */
            selected_24h: number;
            /** Screened Out 24H */
            screened_out_24h: number;
            /** Failed Pending */
            failed_pending: number;
            /** Queued Jobs */
            queued_jobs: number;
            /** Running Jobs */
            running_jobs: number;
        };
        /** SourceBrief */
        SourceBrief: {
            /** Id */
            id: number;
            /** Key */
            key: string;
            /** Name */
            name: string;
            /** Tier */
            tier: string;
        };
        /** SourceOut */
        SourceOut: {
            /** Id */
            id: number;
            /** Key */
            key: string;
            /** Name */
            name: string;
            /** Kind */
            kind: string;
            /** Url */
            url: string;
            /** Tier */
            tier: string;
            /** Category */
            category: string;
            /** Enabled */
            enabled: boolean;
            /** Interval Min */
            interval_min: number;
            /** Notes */
            notes: string | null;
            /** Last Run At */
            last_run_at: string | null;
            /** Last Ok At */
            last_ok_at: string | null;
            /** Last Error */
            last_error: string | null;
            /** Fail Streak */
            fail_streak: number;
            /**
             * Runs 24H
             * @default 0
             */
            runs_24h: number;
            /**
             * Ok 24H
             * @default 0
             */
            ok_24h: number;
            /**
             * New 7D
             * @default 0
             */
            new_7d: number;
            /**
             * Selected 7D
             * @default 0
             */
            selected_7d: number;
        };
        /** SourcePatch */
        SourcePatch: {
            /** Enabled */
            enabled?: boolean | null;
            /** Interval Min */
            interval_min?: number | null;
        };
        /** SourceRunOut */
        SourceRunOut: {
            /** Id */
            id: number;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Duration Ms */
            duration_ms: number;
            /** Transport Status */
            transport_status: string;
            /** Parse Status */
            parse_status: string;
            /** Http Status */
            http_status: number | null;
            /** Fetched */
            fetched: number;
            /** New Count */
            new_count: number;
            /** Error */
            error: string | null;
        };
        /**
         * Stage
         * @enum {string}
         */
        Stage: "planning" | "approval" | "feasibility" | "tendering" | "awarded" | "construction" | "operation" | "unknown";
        /** StoryBrief */
        StoryBrief: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Item Count */
            item_count: number;
            /** Source Count */
            source_count: number;
            /** Heat */
            heat: number;
            /** Status */
            status: string;
        };
        /** StoryDetail */
        StoryDetail: {
            story: components["schemas"]["StoryBrief"];
            /** Digest */
            digest: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /** Timeline */
            timeline: components["schemas"]["ItemCard"][];
        };
        /** Tuning */
        Tuning: {
            /**
             * Profile
             * @default 公司定位：电力基建领域的集成商，全国范围承接业务。
             *     业务线 1 —— 智能运检 / AI 视觉：输电线路与变电站的无人机巡检、布控球与视频监控、在线监测、施工现场安监识别（安全帽/违章/入侵）、边缘计算终端与 AI 识别平台。
             *     业务线 2 —— 输变电工程施工 / EPC：110kV 及以上变电站新建扩建、输电线路、配网改造工程的施工总承包与 EPC。
             *     最关心：国网/南网及省公司、发电集团、地方政府的相关招标采购与中标结果；变电站/线路项目的核准、可研与开工（可提前介入）；电网投资规划与数字化/智能化政策。
             */
            profile: string;
            /**
             * Focus
             * @default 智能运检/AI 视觉、输变电工程 EPC
             */
            focus: string;
            weights?: components["schemas"]["DimWeights"];
            /** Tier Coef */
            tier_coef?: {
                [key: string]: number;
            };
            /** Thresholds */
            thresholds?: {
                [key: string]: number;
            };
            /**
             * Hype Penalty
             * @default 0.7
             */
            hype_penalty: number;
            /**
             * Lead Notify Min Match
             * @default 60
             */
            lead_notify_min_match: number;
            /**
             * Story Similarity
             * @default 0.86
             */
            story_similarity: number;
        };
        /** UsageDay */
        UsageDay: {
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Task */
            task: string;
            /** Calls */
            calls: number;
            /** Failures */
            failures: number;
            /** Prompt Tokens */
            prompt_tokens: number;
            /** Completion Tokens */
            completion_tokens: number;
            /** Cost Yuan */
            cost_yuan: number;
        };
        /** UsageOut */
        UsageOut: {
            /** Days */
            days: components["schemas"]["UsageDay"][];
            /** Recent Errors */
            recent_errors: {
                [key: string]: unknown;
            }[];
        };
        /** V1Digest */
        V1Digest: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "daily" | "weekly";
            /**
             * Date
             * Format: date
             * @description 期号日期（日报为当天 08:00 截止的那一天）
             */
            date: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /** Issue No */
            issue_no: number;
            /** Title */
            title: string;
            /** Lead Title */
            lead_title: string | null;
            /** Item Count */
            item_count: number;
            /** Url */
            url: string;
            /** Overview */
            overview: string | null;
            /** Sections */
            sections: components["schemas"]["V1DigestSection"][];
            /** Markdown */
            markdown: string;
        };
        /** V1DigestBrief */
        V1DigestBrief: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "daily" | "weekly";
            /**
             * Date
             * Format: date
             * @description 期号日期（日报为当天 08:00 截止的那一天）
             */
            date: string;
            /**
             * Period End
             * Format: date
             */
            period_end: string;
            /** Issue No */
            issue_no: number;
            /** Title */
            title: string;
            /** Lead Title */
            lead_title: string | null;
            /** Item Count */
            item_count: number;
            /** Url */
            url: string;
        };
        /** V1DigestSection */
        V1DigestSection: {
            /** Name */
            name: string;
            /** Comment */
            comment: string;
            /** Items */
            items: components["schemas"]["V1Item"][];
        };
        /** V1HotStory */
        V1HotStory: {
            /** Rank */
            rank: number;
            /** Story Id */
            story_id: number;
            /** Title */
            title: string;
            /** Url */
            url: string;
            /** Heat */
            heat: number;
            /** Source Count */
            source_count: number;
            /** Item Count */
            item_count: number;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /**
             * Is New
             * @description 6 小时内首次出现
             */
            is_new: boolean;
            lead_item: components["schemas"]["V1Item"];
        };
        /** V1Item */
        V1Item: {
            /** Id */
            id: number;
            /**
             * Title
             * @description 中文短标题（模型根据原文改写）
             */
            title: string;
            /** Original Title */
            original_title: string;
            /**
             * Url
             * @description 站内阅读页
             */
            url: string;
            /**
             * Source Url
             * @description 原文链接
             */
            source_url: string;
            /** Source */
            source: string;
            /**
             * Tier
             * @description 信源档位：T1 官方一手 / T1_5 专业媒体 / T2 综合媒体
             */
            tier: string;
            channel: components["schemas"]["Channel"];
            /** Province */
            province: string | null;
            /** Summary */
            summary: string | null;
            /**
             * Reason
             * @description 推荐理由
             */
            reason: string | null;
            /**
             * Action
             * @description 建议动作
             */
            action: string | null;
            /** Tags */
            tags: string[];
            /**
             * Score
             * @description AI 评分 0–100
             */
            score: number | null;
            /** Selected */
            selected: boolean;
            /** Published At */
            published_at: string | null;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /** Story Id */
            story_id: number | null;
            /**
             * Also Reported
             * @description 另有几家信源报道了同一件事
             */
            also_reported: number;
            lead: components["schemas"]["V1Lead"] | null;
        };
        /** V1ItemPage */
        V1ItemPage: {
            /** Items */
            items: components["schemas"]["V1Item"][];
            /**
             * Next Cursor
             * @description 下一页游标；为空表示没有更多
             */
            next_cursor: string | null;
        };
        /** V1Knowledge */
        V1Knowledge: {
            /** Id */
            id: number;
            /**
             * Title
             * @description 中文短标题（模型改写，去掉标题党）
             */
            title: string;
            /** Original Title */
            original_title: string;
            /**
             * Url
             * @description 站内知识卡片页
             */
            url: string;
            /**
             * Source Url
             * @description 原文链接
             */
            source_url: string;
            /**
             * Account
             * @description 公众号 / 作者 / 站点
             */
            account: string | null;
            /** Published At */
            published_at: string | null;
            domain: components["schemas"]["KnowledgeDomain"];
            ktype: components["schemas"]["KnowledgeType"];
            /** Tags */
            tags: string[];
            /** Summary */
            summary: string | null;
            /**
             * Key Points
             * @description 3–5 条核心要点，仅来自原文
             */
            key_points: string[];
            /**
             * Scenarios
             * @description 适用场景
             */
            scenarios: string | null;
            /**
             * Solution Use
             * @description 可用于哪类方案的哪一部分
             */
            solution_use: string | null;
            /**
             * Standards
             * @description 原文出现的标准规范编号（已回原文核验）
             */
            standards: string[];
            /**
             * Score
             * @description 质量分 0–100（深度、实用性、准确性、原创性）
             */
            score: number | null;
            /** Featured */
            featured: boolean;
        };
        /** V1KnowledgePage */
        V1KnowledgePage: {
            /** Items */
            items: components["schemas"]["V1Knowledge"][];
            /** Total */
            total: number;
        };
        /** V1Lead */
        V1Lead: {
            /** Project Name */
            project_name: string | null;
            /**
             * Owner
             * @description 业主 / 招标人
             */
            owner: string | null;
            /** Province */
            province: string | null;
            /** Voltage Kv */
            voltage_kv: number | null;
            /**
             * Amount Wan
             * @description 金额（万元）
             */
            amount_wan: number | null;
            stage: components["schemas"]["Stage"];
            /**
             * Bid No
             * @description 招标 / 项目编号
             */
            bid_no: string | null;
            /**
             * Deadline At
             * @description 投标截止时间
             */
            deadline_at: string | null;
            /** Qualification */
            qualification: string | null;
            /**
             * Winner
             * @description 中标人（中标公示才有）
             */
            winner: string | null;
            biz_line: components["schemas"]["BizLine"];
            /**
             * Match Score
             * @description 与站点业务画像的匹配度 0–100
             */
            match_score: number;
        };
        /** V1LeadPage */
        V1LeadPage: {
            /** Items */
            items: components["schemas"]["V1Item"][];
            /** Total */
            total: number;
        };
        /** V1Story */
        V1Story: {
            /** Id */
            id: number;
            /** Title */
            title: string;
            /** Url */
            url: string;
            /**
             * Digest
             * @description AI 综述
             */
            digest: string | null;
            /** Source Count */
            source_count: number;
            /** Item Count */
            item_count: number;
            /**
             * First Seen At
             * Format: date-time
             */
            first_seen_at: string;
            /**
             * Last Seen At
             * Format: date-time
             */
            last_seen_at: string;
            /**
             * Timeline
             * @description 按时间正序，最多最近 50 条
             */
            timeline: components["schemas"]["V1Item"][];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** Viewer */
        Viewer: {
            /** Admin */
            admin: boolean;
            /** Auth Required */
            auth_required: boolean;
        };
        /** WatchRuleIn */
        WatchRuleIn: {
            /** Name */
            name: string;
            /** Keywords */
            keywords?: string[];
            /** Provinces */
            provinces?: string[];
            /** Channels */
            channels?: components["schemas"]["Channel"][];
            /** Min Amount Wan */
            min_amount_wan?: number | string | null;
            /** Min Voltage Kv */
            min_voltage_kv?: number | null;
            /**
             * Notify
             * @default true
             */
            notify: boolean;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
        };
        /** WatchRuleOut */
        WatchRuleOut: {
            /** Name */
            name: string;
            /** Keywords */
            keywords: string[];
            /** Provinces */
            provinces: string[];
            /** Channels */
            channels: components["schemas"]["Channel"][];
            /** Min Amount Wan */
            min_amount_wan: string | null;
            /** Min Voltage Kv */
            min_voltage_kv: number | null;
            /**
             * Notify
             * @default true
             */
            notify: boolean;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /** Id */
            id: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Viewer"];
                };
            };
        };
    };
    list_items_api_items_get: {
        parameters: {
            query?: {
                view?: "selected" | "all" | "starred" | "screened";
                channel?: components["schemas"]["Channel"] | null;
                province?: string | null;
                source_id?: number | null;
                q?: string | null;
                since?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ItemCard_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_api_items_search_get: {
        parameters: {
            query: {
                q: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemCard"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    items_by_ids_api_items_by_ids_get: {
        parameters: {
            query: {
                ids: number[];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemCard"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_item_api_items__item_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_item_api_items__item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ItemPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ItemCard"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_leads_api_leads_get: {
        parameters: {
            query?: {
                stage?: components["schemas"]["Stage"][] | null;
                province?: string[] | null;
                biz_line?: components["schemas"]["BizLine"][] | null;
                follow?: components["schemas"]["FollowStatus"][] | null;
                min_amount_wan?: number | string | null;
                min_voltage_kv?: number | null;
                open_only?: boolean;
                q?: string | null;
                sort?: "recent" | "deadline" | "amount" | "match";
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LeadPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lead_provinces_api_leads_provinces_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": string[];
                };
            };
        };
    };
    hot_api_hot_get: {
        parameters: {
            query?: {
                hours?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HotStory"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    story_detail_api_stories__story_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_digests_api_digests_get: {
        parameters: {
            query?: {
                kind?: components["schemas"]["DigestKind"];
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DigestBrief"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    latest_digest_api_digests__kind__latest_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kind: components["schemas"]["DigestKind"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DigestDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_digest_api_digests__kind___period_start__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                kind: components["schemas"]["DigestKind"];
                period_start: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DigestDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_knowledge_api_knowledge_get: {
        parameters: {
            query?: {
                domain?: components["schemas"]["KnowledgeDomain"] | null;
                ktype?: components["schemas"]["KnowledgeType"] | null;
                q?: string | null;
                featured?: boolean;
                sort?: "score" | "recent";
                status?: components["schemas"]["ArticleStatus"] | null;
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgePage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_knowledge_api_knowledge_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgeSubmit"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeSubmitAck"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    knowledge_facets_api_knowledge_facets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeFacets"];
                };
            };
        };
    };
    related_to_item_api_knowledge_related_get: {
        parameters: {
            query: {
                item_id: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeCard"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_knowledge_api_knowledge__article_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_knowledge_api_knowledge__article_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_knowledge_api_knowledge__article_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KnowledgePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KnowledgeCard"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    meta_api_meta_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Meta"];
                };
            };
        };
    };
    submit_feedback_api_site_feedback_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackAck"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_items_api_v1_items_get: {
        parameters: {
            query?: {
                mode?: "selected" | "all";
                window?: "24h" | "7d";
                channel?: components["schemas"]["Channel"] | null;
                /** @description 标题或摘要包含的关键词 */
                q?: string | null;
                cursor?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1ItemPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_search_api_v1_search_get: {
        parameters: {
            query: {
                q: string;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1Item"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_leads_api_v1_leads_get: {
        parameters: {
            query?: {
                stage?: components["schemas"]["Stage"] | null;
                province?: string | null;
                biz_line?: components["schemas"]["BizLine"] | null;
                /** @description 只看未截止（无截止时间的也保留） */
                open_only?: boolean;
                min_amount_wan?: number | string | null;
                min_voltage_kv?: number | null;
                q?: string | null;
                sort?: "recent" | "deadline" | "amount";
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1LeadPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_hot_stories_api_v1_hot_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1HotStory"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_story_detail_api_v1_stories__story_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1Story"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_knowledge_list_api_v1_knowledge_get: {
        parameters: {
            query?: {
                domain?: components["schemas"]["KnowledgeDomain"] | null;
                ktype?: components["schemas"]["KnowledgeType"] | null;
                /** @description 标题、摘要、要点、标签包含的关键词 */
                q?: string | null;
                sort?: "score" | "recent";
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1KnowledgePage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_dailies_api_v1_dailies_get: {
        parameters: {
            query?: {
                kind?: components["schemas"]["DigestKind"];
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1DigestBrief"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_daily_latest_api_v1_dailies_latest_get: {
        parameters: {
            query?: {
                kind?: components["schemas"]["DigestKind"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1Digest"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    v1_daily_api_v1_dailies__day__get: {
        parameters: {
            query?: {
                kind?: components["schemas"]["DigestKind"];
            };
            header?: never;
            path: {
                day: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["V1Digest"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_lead_api_leads__item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LeadPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LeadOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_api_digests__kind__generate_post: {
        parameters: {
            query: {
                period_start: string;
            };
            header?: never;
            path: {
                kind: components["schemas"]["DigestKind"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_knowledge_api_knowledge__article_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_feedback_api_feedback_get: {
        parameters: {
            query?: {
                status?: ("new" | "done") | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    patch_feedback_api_feedback__feedback_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                feedback_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackPatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    gold_stats_api_gold_stats_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoldStats"];
                };
            };
        };
    };
    gold_next_api_gold_next_get: {
        parameters: {
            query?: {
                skip?: number[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoldCase"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    gold_case_api_gold__item_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoldCase"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_label_api_gold__item_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GoldLabelIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoldStats"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_label_api_gold__item_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoldStats"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_api_eval_runs_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvalRunBrief"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_run_api_eval_runs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvalRunIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_eval_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvalRunDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sources_api_sources_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceOut"][];
                };
            };
        };
    };
    patch_source_api_sources__source_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourcePatch"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    collect_now_api_sources__source_id__collect_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    source_runs_api_sources__source_id__runs_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                source_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceRunOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_rules_api_watch_rules_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WatchRuleOut"][];
                };
            };
        };
    };
    create_rule_api_watch_rules_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WatchRuleIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WatchRuleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_rule_api_watch_rules__rule_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WatchRuleIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WatchRuleOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_rule_api_watch_rules__rule_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rule_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_tuning_api_tuning_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Tuning"];
                };
            };
        };
    };
    put_tuning_api_tuning_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Tuning"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Tuning"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    usage_api_usage_get: {
        parameters: {
            query?: {
                days?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UsageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pipeline_stats_api_pipeline_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PipelineStats"];
                };
            };
        };
    };
    list_jobs_api_jobs_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["JobStatus"] | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_failed_items_api_items_retry_failed_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Ok"];
                };
            };
        };
    };
}
