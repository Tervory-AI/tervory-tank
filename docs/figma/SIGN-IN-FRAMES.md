# Sign-in frames — Proposed, not approved

Design only. No authentication implementation, runtime configuration, secrets, live data or emails are changed. Target: unmodified self-hosted Zitadel Login V2, upstream reference `0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84`.

Figma file: `ZnphBOJU6657tohGLD3IzS`; page **8 · Sign-in**, node `237:9`. Every screen, email and proposed word awaits founder approval. Invented client **Morrow Field** is an example for Figma only.

## Exactly what is configurable

- Instance defaults and organization overrides. The effective branding is selected by the authorization request's organization scope and project branding behavior.
- `lightTheme.logoUrl`, `darkTheme.logoUrl`: separately uploaded original logos; `lightTheme.iconUrl`, `darkTheme.iconUrl`: separately uploaded icons. Icons are browser/small-surface assets, not an extra decorative control inside the form.
- Each theme exposes only `backgroundColor`, `primaryColor`, `warnColor`, `fontColor`. Login derives its shade ramps, contrast and secondary text from those values; card and input surfaces are not independent brand settings.
- `fontUrl`: one uploaded custom UI font. Inter is proposed for the entire login; separate Jost headings cannot be configured through this single setting. Logos retain their own original artwork. Email font support depends on the mail client; the native template's fallback family remains applicable.
- `hideLoginNameSuffix`, `disableWatermark`, `themeMode` (`LIGHT`, `DARK`, `AUTO`/unspecified). Proposals use hidden suffix/watermark and show both light and dark. Existing language/theme controls remain native chrome.
- Login V2 text overrides: `PUT /v2/settings/hosted_login_translation`, scoped with `instance: true` or `organizationId`, plus `locale: "en"` and `translations` containing actual locale namespaces/keys. The old Console login-text editor does not configure Login V2.
- Email messages: `SetCustomVerifyEmailMessageText`, `SetCustomPasswordResetMessageText`, `SetCustomInitMessageText`. Each accepts `title`, `preHeader`, `subject`, `greeting`, `text`, `buttonText`, `footerText`, scoped to a language and organization (instance equivalents also exist). Native message types: `VerifyEmail`, `PasswordReset`, `InitCode`. Preserve supported Go-template substitutions such as `{{.DisplayName}}`, `{{.Code}}`, `{{.PreferredLoginName}}`. The action URL is supplied by Zitadel, not invented in the design.
- Email subject/preheader/title are shown as Figma review metadata, not invented body elements. The native email body supplies logo, greeting, text, action and optional footer; its outer width, 180px logo, typography and spacing remain the native template. Email dark appearance is a review of its dark branding values, not a claim that every email client follows a live theme switch.

## Native constraints, not new settings

The default Login app uses its existing `top-to-bottom` / `flat` / `regular` layout, 440px outer wrapper, 16px wrapper gutters, 24px horizontal and 32px vertical card padding, 24px heading and 40px input. These are upstream defaults, not branding sliders. No custom CSS, two-column marketing panel, product navigation, new authentication method, new button or custom browser passkey dialog is proposed.

Native flow prerequisites (not changed here): local username/password authentication enabled; email login enabled and phone login disabled for the requested “email or username” label; registration and external providers not enabled in these views; password reset visible; an enrolled passkey/TOTP for those requested steps. These are existing login-policy choices, not merely branding. Data placeholders represent native runtime values and are not real accounts or secrets.

**Device denial limit:** current `denyDeviceAuthorization` returns to `/device` through the native consent component fallback. No dedicated denied-confirmation page or translation key exists. The requested post-denial frame therefore shows the actual code-entry screen, with a Figma-only annotation explaining the return. It does not invent a “Device denied” message inside the live UI. Approval uses the native `/signedin` page; its close-window notice is hardcoded upstream and must remain unchanged under this brief.

**Error limits:** backend error descriptions such as `Errors.User.Locked` and `Errors.User.Code.Expired` are upstream, read-only messages, not Hosted Login Translation overrides. Where shown, the exact existing wording is retained and mapped as read-only. It is not falsely presented as a new configurable key. Wrong-password fallback copy uses the actual `password.verify.errors.couldNotVerifyPassword` / authentication-error keys.

**Passkey limit:** the operating-system/browser verification sheet is outside Zitadel branding and is not drawn. Only the existing Login app passkey page and controls are proposed.

All frame status ribbons, client-example labels, screen IDs, state captions and mapping notes are Figma-only review annotations. They are explicitly excluded from deployable message texts. Each text layer is named with its source key or `FIXED`/`FIGMA ONLY` provenance.

## Primary sources read before drawing

- [Branding settings](https://zitadel.com/docs/guides/manage/customize/branding)
- [Customized message/login texts](https://zitadel.com/docs/guides/manage/customize/texts)
- [Hosted Login V2 translation mechanism](https://zitadel.com/docs/guides/integrate/login/hosted-login)
- [Get Branding Settings schema](https://zitadel.com/docs/reference/api/settings/zitadel.settings.v2.SettingsService.GetBrandingSettings)
- [Set Hosted Login Translation](https://zitadel.com/docs/reference/api/settings/zitadel.settings.v2.SettingsService.SetHostedLoginTranslation)
- [Init email fields](https://zitadel.com/docs/reference/api/management/zitadel.management.v1.ManagementService.SetCustomInitMessageText)
- [Password-reset email fields](https://zitadel.com/docs/reference/api/management/zitadel.management.v1.ManagementService.SetCustomPasswordResetMessageText)
- [Verify-email fields](https://zitadel.com/docs/reference/api/management/zitadel.management.v1.ManagementService.SetCustomVerifyEmailMessageText)
- [Actual V2 locale keys](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/locales/en.json)
- [Native Login layout](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/components/dynamic-theme.tsx), [default theme](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/lib/theme.ts), [derived colours](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/helpers/colors.ts)
- [Native consent actions](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/components/consent.tsx), [device outcomes](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/lib/server/device.ts), [signed-in page](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/apps/login/src/app/(login)/signedin/page.tsx)
- [Backend error descriptions](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/internal/static/i18n/en.yaml)
- [Native email template](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/internal/notification/static/templates/template.html), [message fields](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/proto/zitadel/management.proto), [email substitutions](https://github.com/zitadel/zitadel/blob/0c0ee1dab9ed2fdeb8b4736641ee34d84c895f84/internal/notification/static/i18n/en.yaml)

## Frame register

Creation in progress. Final node IDs and exact element mappings will replace this checkpoint before completion.
