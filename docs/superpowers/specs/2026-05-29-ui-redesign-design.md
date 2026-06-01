# UI Redesign Design Spec

**Date:** 2026-05-29  
**Project:** VietNamLaw / LexVN frontend  
**Scope:** Redesign chat and auth UI, introduce multi-session chat shell, and define MagicPath component deliverables for implementation

## 1. Goal

Redesign the LexVN frontend so it feels like a premium legal intelligence workspace rather than a single-page chatbot with decorative styling.

The redesign covers:
- the main chat page at `frontend/app/page.tsx`
- the auth page at `frontend/app/auth/page.tsx`
- a shared visual language across both pages
- a new multi-session chat layout using backend APIs that already exist in `frontend/lib/api.ts`
- a MagicPath-first component breakdown so the UI can be designed as reusable modules before implementation in Next.js

The redesign does **not** change backend answer generation behavior or add backend endpoints.

## 2. Current State Summary

### Chat page
The current chat page is a single centered column with:
- inline CSS embedded directly in `frontend/app/page.tsx`
- one active session stored in localStorage
- no visible session history UI despite existing backend session APIs
- header actions for new chat, logout, and theme toggle
- suggestion cards, markdown-rendered assistant bubbles, and a bottom composer

### Auth page
The current auth page already uses a split layout with:
- left-side hero and right-side login/register panel
- consistent brand palette and typography with the chat page
- inline CSS embedded directly in `frontend/app/auth/page.tsx`

### Structural issue
Both pages currently mix layout, interaction logic, and visual styling inside page-level files. This makes iteration difficult and prevents a clean MagicPath component workflow.

## 3. Design Direction

The approved direction is **editorial luxury**.

This means the UI should feel closer to a high-end legal publication or modern law-firm workspace than a generic AI chat interface.

### Visual characteristics
- warm ivory / parchment light backgrounds
- espresso / walnut / antique brass dark mode
- restrained gold accents used for emphasis, not saturation
- strong contrast between editorial display typography and operational UI text
- softer, more mature surfaces with thin borders and subtle depth
- motion that feels quiet and deliberate rather than playful

### Typography
- keep `Cormorant Garamond` for display headings and key brand moments
- keep `DM Sans` for body copy, controls, labels, and operational text
- increase hierarchy between page headlines, panel headings, metadata, and utility controls

## 4. Functional Scope

The redesign will include the following functional changes:

### Included
- multi-session sidebar on the chat page
- session switching
- session rename
- session delete
- new session creation
- assistant answer copy action
- export current session to Markdown
- profile dropdown replacing the standalone logout emphasis
- refined source display for assistant messages
- responsive adaptation for desktop and mobile

### Excluded
- backend changes
- bookmarks requiring new persistence
- PDF export
- follow-up suggestion generation after each answer
- right-side deep source analysis drawer that requires additional source modeling

## 5. Chat Page Architecture

The chat page will move from a single-column shell to a three-zone shell.

### 5.1 Left Sidebar
A persistent sidebar on desktop and a slide-over drawer on mobile.

Responsibilities:
- display brand and workspace identity
- provide a primary “new consultation” / “new chat” action
- list recent sessions
- show active session clearly
- expose rename, delete, and export actions per session or from contextual menus

Expected content of each session item:
- session title
- short preview or fallback label
- relative time metadata if available or derivable
- active styling for current session

### 5.2 Main Conversation Column
The main reading and interaction area.

Responsibilities:
- display topbar with current session context
- show welcome state when no messages exist
- render conversation in a wider, more legible editorial reading column
- preserve markdown rendering and source visibility
- support per-answer actions such as copy

The conversation area should feel less like a messaging app and more like a legal drafting surface.

### 5.3 Bottom Composer
A docked composer anchored to the bottom of the conversation area.

Responsibilities:
- preserve current Enter / Shift+Enter behavior
- support loading state clearly
- provide a calmer, more premium interaction model
- keep the legal disclaimer present but less visually heavy

## 6. Chat Interaction Model

### Session-first navigation
The current `SESSION_KEY` storage mechanism will become a first-class navigation concept rather than a hidden implementation detail.

Expected behavior:
- loading the page restores the active session if available
- selecting a session loads its messages
- creating a new session clears the active conversation view and starts a fresh thread
- deleting the current session transitions predictably to another valid session or an empty welcome state
- renaming should update both sidebar state and visible topbar title immediately

### Assistant message behavior
Assistant bubbles should support:
- richer typographic treatment of markdown
- copy action
- more refined source presentation than the current plain joined string

### Welcome state
The empty-state experience should remain useful, but feel more premium and intentional.

It should include:
- an editorial headline
- a concise legal positioning statement
- curated prompt cards aligned to high-value legal intents

## 7. Auth Page Design

The auth page will keep its successful two-column structure, but be visually and typographically refined to match the redesigned chat shell.

### Left Hero Panel
The hero should communicate trust, continuity, and premium positioning.

It should contain:
- stronger editorial headline
- tighter supporting copy
- refined legal trust markers or practice pillars
- a quote or statement that reinforces continuity and legal reasoning

The current stat cards should be redesigned to feel less like dashboard widgets and more like trust-oriented content blocks.

### Right Auth Panel
The form panel should become more minimal and refined.

It should include:
- login/register tab switcher with quieter styling
- cleaner form fields and spacing
- more polished validation and success states
- a stronger but more restrained primary CTA

The auth experience should feel like entering a private legal workspace rather than signing up for a consumer SaaS product.

## 8. Shared Visual System

A shared visual system should be established so the chat and auth pages no longer define their look independently inside large inline style blocks.

### Token categories
Implementation should introduce shared tokens for:
- background colors
- surface colors
- border colors
- primary accent colors
- text hierarchy colors
- shadows
- radii
- transition timing
- typography assignments

### Design principles
- gold is an accent, not a default fill color everywhere
- surfaces should emphasize restraint and clarity
- UI chrome should recede so content and legal reasoning feel central
- readability takes priority over ornamental density

## 9. MagicPath Component Deliverables

The approved MagicPath workflow is component-first, not page-first.

The design deliverables should therefore be authored as reusable MagicPath components rather than only two large full-page frames.

### Planned components
1. `ChatSidebar`
2. `ChatSessionItem`
3. `ChatTopbar`
4. `WelcomeState`
5. `AssistantMessageBubble`
6. `UserMessageBubble`
7. `ChatComposer`
8. `ProfileDropdown`
9. `AuthHero`
10. `AuthPanel`

These components will later be composed into:
- a chat shell
- an auth shell

### Reason for this breakdown
This structure maps well to:
- MagicPath’s component-oriented workflow
- the user’s request for modular design work
- future maintainability in the Next.js codebase
- the need to refactor away from page-level styling blobs

## 10. Data and API Integration Boundaries

Implementation may use only APIs that already exist in `frontend/lib/api.ts`.

Relevant existing functions include:
- `listSessions`
- `getSession`
- `renameSession`
- `deleteSession`
- `getMessages`
- `createSession`
- `sendAuthedMessage`
- `resetSession`

No new backend contract is required for the approved v1 scope.

Export to Markdown should be implemented on the frontend from currently loaded session data.

## 11. Preservation Requirements

The redesign must preserve the following working behaviors:
- login flow
- register flow
- auth persistence
- theme persistence
- markdown rendering for assistant messages
- unauthorized redirect handling
- session-not-found recovery behavior
- textarea auto-resize behavior
- Enter to send and Shift+Enter for line breaks

This is a redesign plus UI capability expansion, not a rewrite of business behavior.

## 12. Responsive Expectations

### Desktop
- left sidebar visible
- main conversation column centered within remaining width
- topbar and composer aligned with conversation shell

### Mobile
- sidebar becomes a drawer
- topbar remains compact and actionable
- composer remains accessible without consuming excessive vertical space
- session operations remain reachable without hover dependence

## 13. Verification Requirements

The implementation plan must include verification for:
- session list load behavior
- switching between sessions
- rename session behavior
- delete session behavior
- new session behavior
- export Markdown behavior for the active session
- copy action on assistant messages
- auth login/register flow
- theme consistency across `/` and `/auth`
- desktop and mobile layout integrity

## 14. Rollout Strategy

Implementation should be split into three stages:

### Stage 1: Shared visual system and layout primitives
Create the design tokens, shared structural pieces, and styling foundations.

### Stage 2: Chat shell redesign
Implement sidebar, topbar, session-aware shell, message presentation refresh, composer redesign, and auxiliary actions.

### Stage 3: Auth redesign and final polish
Refine the auth page using the shared system, then run cross-page consistency and regression verification.

## 15. Recommendation

Proceed with a component-first MagicPath workflow, then map those components back into the Next.js frontend through a staged implementation plan.

This gives the best balance of:
- visual quality
- maintainability
- alignment with MagicPath’s strengths
- minimal backend risk
- room for iterative refinement after the first redesign pass
