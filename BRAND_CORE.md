# JBSN Brand Core — Digital Implementation Standard

**Status:** Master reference — the founder-supplied “JBSN World.png” ecosystem board is the visual source of truth. Preserve its three original brand identities and layouts.  
**Applies to:** JBSN World, JBSN AI OS™, JBSN Creative™, Command Centre, websites, dashboards, proposals, social profiles and future subsidiary touchpoints.

## Brand architecture

- **JBSN World** — parent holding company and corporate trust mark.
- **JBSN Creative™** — first operating/revenue business; keep its own distinct creative identity.
- **JBSN AI OS™** — internal operating infrastructure; technical, precise, secure and executive-grade.
- **Future subsidiaries** — individual market-facing identities, endorsed by JBSN World where appropriate.

Do not collapse the three identities into one generic logo. Use the correct identity for the context and keep a consistent family resemblance through spacing, typography quality, tone and disciplined use of the parent palette.

## Brand idea

**JBSN World tagline:** *Ideas. Intelligence. Impact.*  
**Operating principle:** *Humans govern. AI operates. Systems enforce. Data measures.*

The visual tone is professional, ambitious, intelligent, trustworthy and global. Avoid toy-like gradients, random icon styles, excessive glow, inconsistent accent colors and decorative complexity that reduces clarity.

## Color tokens

### JBSN World — corporate identity
- Black / near-black: #070A0F
- Metallic gold: #D4AF37 (use gold shades visible in the supplied master artwork)
- White: #F5F7FA
- Secondary text: #9AA8B7
- Typography: Montserrat Bold

Use navy/ink as the foundation, orange-gold for emphasis and white for clarity. Preserve the founder-supplied official circular mark and JBSN/WORLD lock-up wherever its original artwork is available; do not redraw or distort that master logo.

### JBSN AI OS™ — product/interface identity
- Core background: #070A0F
- Surface: #0D121A
- Electric blue: #168CFF
- White: #F5F7FA
- Typography: Inter Semi Bold
- Main text: #F5F7FA
- Muted text: #9AA8B7
- Success: #55D6A2
- Warning: #FFC66D
- Error: #FF7D88

Cyan is the AI OS interface accent; orange-gold is reserved for parent-brand signals, key highlights and important decisions. Do not use cyan as a replacement for JBSN World's orange-gold in corporate collateral.

### JBSN Creative™
- Core background: #070A0F
- Purple: #7C3AED
- Magenta: #FF00E1
- White: #FFFFFF
- Typography: Poppins Bold
- Keep the exact purple geometric play-mark and wordmark treatment shown in the supplied master reference.

## Typography

- Preferred UI family: **Inter** (or a close system sans-serif fallback).
- Headings: strong weight, tight but readable tracking, clear hierarchy.
- Body: comfortable line-height and restrained text widths.
- Technical IDs/logs: monospaced type only where it improves scanning.
- Use consistent title case; use uppercase sparingly for small section labels.

## Logo usage

1. Use the supplied official JBSN World logo asset for corporate-facing materials when available.
2. Use the JBSN AI OS emblem for the operating system, runtime and Command Centre.
3. Keep logo clear space at least the height of the circular mark's inner symbol.
4. Never stretch, skew, recolor arbitrarily, add effects to, or place a logo on a low-contrast background.
5. Provide light and dark variants for production use; ensure small-size legibility and a monochrome fallback.
6. The supplied “JBSN World.png” ecosystem board is the design authority. SVG concepts and CSS marks must never replace the exact master logo artwork when that artwork can be used.

## Working JBSN World vector identity — v1

The founder requested a professional JBSN World logo and a consistent application across the World website, founder HQ, and JBSN AI OS. The previously referenced founder-supplied ecosystem board remains unavailable; this original vector direction is therefore a proposed working identity pending founder review, not a claim that the missing master was recovered or that a trademark is registered.

The mark uses an open meridian circle around a J monogram, with a restrained metallic-gold point. JBSN World uses near-black, gold, and white; JBSN AI OS carries the same geometry with electric blue as its product signal. JBSN Creative retains its separate purple/magenta identity.

Source assets are in assets/brand/: jbsn-world-symbol.svg, light/dark JBSN World lockups, the favicon, jbsn-aios-emblem.svg, and the AIOS product lockup. The AIOS dashboard uses the inline product emblem so it remains available under the current runtime's content policy.

## Interface design rules

- Dark executive surfaces, subtle borders, restrained depth and generous spacing.
- Use the same radius scale, button styles, form controls, status pills and heading hierarchy across the AI OS.
- Status colors communicate meaning only: green = healthy/success, amber = waiting/warning, red = failure/risk, cyan = technical focus, orange-gold = parent-brand emphasis.
- Design mobile-first; maintain keyboard focus visibility, readable contrast and reduced-motion support.
- Show the real operational state. Never style an unverified subsystem as healthy or imply a feature exists before it is implemented.

## Voice and messaging

- Clear, calm, capable and accountable.
- Prefer specific operational language over hype.
- Do not promise full autonomy when only a subset of workflows is implemented.
- Keep founder oversight explicit for consequential actions such as payments, public communications, production deployments, legal commitments and sensitive data operations.

## Implementation checklist

- [x] Apply dark executive styling and responsive component tokens to the AI OS Command Centre.
- [x] Align the compact AI OS emblem and accents closer to the original blue AI mark.
- [x] Establish consistent interface tokens and responsive component styling in the dashboard.
- [ ] Replace temporary web-emblem artwork with the exact official logo files where needed.
- [ ] Apply the same tokens to separate JBSN World and JBSN Creative web properties after their repository/site sources are connected.
- [ ] Add light logo variants, favicon/app icons, social avatars and export-ready vector masters.
- [ ] Validate the deployed UI on desktop and mobile after merge/deploy.

## Governance

Treat this document as the shared design source of truth. Brand changes should be made here first, then reflected in shared tokens/components rather than patched inconsistently across individual screens.
