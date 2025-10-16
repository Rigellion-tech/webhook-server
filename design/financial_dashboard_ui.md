# Financial Dashboard UI Design

## 1. Experience Goals
- Give customers a clear understanding of their cashflow at-a-glance.
- Surface anomalies (overspending, opportunities to save) without requiring manual digging.
- Encourage healthy financial habits through personalized nudges and actionable insights.
- Provide transparency and control over categorization and budgeting features.

## 2. Primary Personas
| Persona | Goals | Pain Points | Dashboard Needs |
| --- | --- | --- | --- |
| Budget-Minded Professional | Track monthly spending vs. income and savings goals. | Overwhelmed by transaction lists and manual categorizations. | Visual summaries, quick categorization tools, budgeting progress indicator. |
| Goal-Oriented Saver | Wants to hit savings targets and reduce discretionary expenses. | Hard to see which categories consume the most budget. | Savings goal tracker, category spending breakdown, advice on adjusting spend. |
| Convenience Seeker | Prefers automation and quick insights. | Lacks time to review statements. | Smart alerts, external offers, conversational assistance. |

## 3. Information Architecture
1. **Global Header**
   - Product logo + "Financial Dashboard" title.
   - Quick actions: `Add Transaction`, `Adjust Budget`, `Connect Account` (icon buttons).
   - User avatar with overflow menu for settings, alerts, sign out.
2. **Primary Navigation (left rail)**
   - Dashboard (current view)
   - Transactions
   - Budgets
   - Goals
   - Insights & Offers
   - Chatbot Assistant
3. **Content Regions**
   1. Overview KPIs (top row)
   2. Spending & Income Analysis (dual column charts)
   3. Category Breakdown & Alerts (stacked cards)
   4. Transactions & Categorization (table with inline controls)
   5. Smart Insights & Assistant (right rail module)

## 4. Layout Blueprint
```
| Header                                                            |
|-------------------------------------------------------------------|
| Nav | KPI Cards |            Spending vs Income Chart             |
|     |-----------|------------------------------------------------|
|     | Budget Progress | Category Breakdown | Alerts               |
|     |-----------------|--------------------|----------------------|
|     | Monthly Transactions (table w/ inline categorization)      |
|     |-----------------------------------------------------------|
|     | Smart Insights & Chatbot Panel (sticky right rail)         |
```
- Desktop layout uses a 12-column grid with 24px gutters. Primary content area spans columns 3-12 when nav rail open.
- Right rail (columns 9-12) contains insights and chatbot; collapsible on smaller screens.
- Tablet/mobile collapses nav to hamburger and stacks sections vertically with accordion for insights.

## 5. Key Components

### 5.1 KPI Cards (Top Row)
- **Monthly Income**: number + sparkline of last 6 months.
- **Total Expenses**: number, percentage change vs last month, color-coded (green under budget, red over).
- **Savings Goal Progress**: progress bar showing amount saved vs target, with tooltip for time remaining.
- **Net Cashflow**: pill showing `Income - Expenses` with trend arrow.

### 5.2 Spending vs. Income Section
- Dual-axis line + bar combo chart:
  - Bars: Expenses per month (stacked by categories on hover).
  - Line: Monthly income.
- Toggle tabs for `Monthly`, `Quarterly`, `Yearly` views.
- Warning badge appears when expenses exceed income (see warnings system).

### 5.3 Category Breakdown
- Donut chart highlighting percentage of spend per category.
- Legend contains editable category names, color chips, and quick filter toggles.
- Hover reveals absolute amount and share of budget; clicking opens detail drawer with transactions.

### 5.4 Alerts & Warnings
- Card list with severity indicators:
  - **Expense > Income**: red card with call-to-action to review categories.
  - **Budget Threshold**: yellow card when a category exceeds 80% of allocation.
  - **Upcoming Bills**: blue card referencing external data.
- Each card offers recommended actions (e.g., "Reduce entertainment spending by $50 to meet goal").

### 5.5 Transactions Table
- Sticky header with filters: date range, account, category, amount range, text search.
- Columns: Date, Description, Category (dropdown with custom entry), Amount, Notes, Feedback.
- Inline tags showing automation status (`Auto`, `Manual`, `Suggested`).
- Row actions: `Split`, `Attach Receipt`, `Flag`. Edited categories sync to analytics instantly.
- Right side panel surfaces contextual insight when rows selected.

### 5.6 Category Customization Modal
- Accessible from transactions or settings.
- Features: add custom category, assign icon/color, set budget limits, reorder via drag-and-drop.
- Shows roll-up totals for merged categories.

### 5.7 External Feedback & Offers
- Card carousel pulling data (e.g., Amazon sale, credit score updates).
- Each card displays source logo, message, and action button ("View Sale", "Learn More").
- Preferences toggle to tailor notifications per merchant or category.

### 5.8 Budget Planner
- Wizard-style form to set monthly income and savings goal.
- Slider for desired savings percentage; auto-calculates recommended category allocations.
- Visual stack bar showing current vs planned distribution; scenario toggle (Conservative, Balanced, Aggressive).

### 5.9 Chatbot Assistant Panel
- Docked panel on right rail with conversation history.
- Quick prompts: "How can I save more this month?", "Explain my entertainment spending", "Suggest budget adjustments".
- Responses pull from transaction data and budgeting rules.
- Supports attachments (e.g., export conversation to PDF) and escalation to human advisor.

## 6. Interaction States
- **Empty State**: when no transactions imported, display illustration with CTA to connect accounts.
- **Loading**: skeleton screens for charts and tables, pulsing placeholders for KPI cards.
- **Error State**: inline error banners with retry buttons.
- **Responsive Behavior**: charts collapse into stacked cards; transactions table becomes swipeable list on mobile.

## 7. Visual Language
- Color Palette: teal primary (`#2AA5A0`), navy secondary (`#1F3B4D`), accent orange for alerts (`#FF8A3D`), success green (`#3AB795`), neutral grays for backgrounds.
- Typography: Sans-serif family (e.g., Inter). Headings bold, body medium, data tables monospace numbers for readability.
- Iconography: outline icons with rounded edges; consistent stroke width.
- Data Visualization: use accessible color contrasts, include data labels on hover and alt text for screen readers.

## 8. Accessibility Considerations
- WCAG AA compliant contrast ratios.
- Keyboard navigable modals and tables.
- Screen reader-friendly labels for charts (ARIA descriptions).
- Provide text alternatives for color-coded statuses (e.g., icon + text).
- Chatbot supports speech-to-text input.

## 9. Notification & Warning System
- Global bell icon with unread badge.
- Inline toast messages for new alerts triggered by rules (income vs expenses, budget thresholds).
- Warning states on KPI cards (e.g., expenses card glows red when over budget) with link to resolution tips.

## 10. Personalization Features
- Persistent user preferences for categories, chart defaults, notifications.
- Allow multiple financial goals, each with progress tracking and milestone reminders.
- External data feed settings to opt in/out of merchant-specific feedback.

## 11. Future Enhancements
- Collaborative budgets for households (shared access).
- Integration with investment accounts for net worth tracking.
- AI-driven forecast of cashflow based on recurring transactions.

