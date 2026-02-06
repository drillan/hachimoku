# Specification Quality Checklist: エージェント定義・ローダー・セレクター

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-02-06
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Assumptions セクションに技術的な実装方針（tomllib, importlib.resources）を記載しているが、これは仕様本体ではなく前提条件の記録であり許容範囲
- ビルトインエージェントのシステムプロンプト内容は実装フェーズで策定するとの前提を明記済み
- file_patterns のマッチング対象（ファイル名部分 vs フルパス）について Assumptions で明確化済み
- model, allowed_tools フィールドの解決は 005-review-engine の責務と明確に分離済み
