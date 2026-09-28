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
         * @description 关键词（pg_trgm 加速）+ 语义（pgvector）混合检索，关键词命中优先。
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
        /**
         * FollowStatus
         * @enum {string}
         */
        FollowStatus: "new" | "watching" | "following" | "ignored" | "closed";
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
                    "application/json": components["schemas"]["Ok"];
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
