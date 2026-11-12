<?php
declare(strict_types=1);

const REPOSITORY = 'https://github.com/ediril/wpsync';
const SITE_DESCRIPTION = 'Pull your WordPress posts into a folder, write in Obsidian or VS Code, preview the diff, then push exactly what you changed.';
const SOCIAL_IMAGE_ALT = 'WPSync terminal session: pull posts, diff, then push to WordPress.';

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function secure_request(): bool
{
    return strtolower((string) ($_SERVER['HTTPS'] ?? '')) === 'on'
        || strtolower((string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')) === 'https';
}

/** The site's origin, or null when the request's host is not a plain host name. */
function site_origin(): ?string
{
    $host = (string) ($_SERVER['HTTP_HOST'] ?? '');
    if (preg_match('/\A[a-z0-9.-]+(?::[0-9]+)?\z/i', $host) !== 1) {
        return null;
    }
    return (secure_request() ? 'https://' : 'http://') . $host;
}

function request_path(): string
{
    $path = parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);
    return is_string($path) && str_starts_with($path, '/') ? $path : '/';
}

function json_ld(array $data): string
{
    $json = json_encode(
        $data,
        JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
            | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
    );
    if ($json === false) {
        throw new RuntimeException('Could not encode structured data.');
    }
    return $json;
}

/**
 * Print the document start through </head>.
 *
 * @param array{title: string, description: string, type: string, structured_data: array} $page
 */
function render_head(array $page): void
{
    $origin = site_origin();
    $canonical = $origin === null ? null : $origin . request_path();
    $image = $origin === null ? null : $origin . '/assets/social-preview.jpg';
    $structuredData = $page['structured_data'];
    if ($image !== null) {
        $structuredData['image'] = $image;
    }
    ?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#080b10">
    <meta name="description" content="<?= h($page['description']) ?>">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="author" content="WPSync contributors">
    <meta property="og:type" content="<?= h($page['type']) ?>">
    <meta property="og:locale" content="en_US">
    <meta property="og:site_name" content="WPSync">
    <meta property="og:title" content="<?= h($page['title']) ?>">
    <meta property="og:description" content="<?= h($page['description']) ?>">
<?php if ($canonical !== null && $image !== null): ?>
    <link rel="canonical" href="<?= h($canonical) ?>">
    <meta property="og:url" content="<?= h($canonical) ?>">
    <meta property="og:image" content="<?= h($image) ?>">
<?php if (secure_request()): ?>
    <meta property="og:image:secure_url" content="<?= h($image) ?>">
<?php endif; ?>
<?php endif; ?>
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="<?= h(SOCIAL_IMAGE_ALT) ?>">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?= h($page['title']) ?>">
    <meta name="twitter:description" content="<?= h($page['description']) ?>">
<?php if ($image !== null): ?>
    <meta name="twitter:image" content="<?= h($image) ?>">
    <meta name="twitter:image:alt" content="<?= h(SOCIAL_IMAGE_ALT) ?>">
<?php endif; ?>
    <script type="application/ld+json"><?= json_ld($structuredData) ?></script>
    <title><?= h($page['title']) ?></title>
    <link rel="describedby" href="/llms.txt" type="text/markdown">
    <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="/assets/favicon-32x32.png" type="image/png" sizes="32x32">
    <link rel="shortcut icon" href="/favicon.ico">
    <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png" sizes="180x180">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&amp;family=Space+Mono:wght@400;700&amp;display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/assets/site.css">
    <script src="/assets/site.js" defer></script>
</head>
<?php
}

function render_header(): void
{
    ?>
    <a class="skip-link" href="#main">Skip to content</a>

    <header class="site-header" data-header>
        <a class="brand" href="/" aria-label="WPSync home">
            <svg class="brand-mark" viewBox="0 0 48 48" aria-hidden="true">
                <path d="M11 6h18l9 9v27H11z" />
                <path d="M29 6v9h9" />
                <path d="M17 24h14M17 30h14M17 36h8" />
            </svg>
            <span>WP<span>Sync</span></span>
        </a>

        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav" data-nav-toggle>
            <span></span><span></span>
            <span class="sr-only">Toggle navigation</span>
        </button>

        <nav class="site-nav" id="site-nav" aria-label="Primary navigation" data-nav>
            <a href="/#workflow">Workflow</a>
            <a href="/#principles">Safety</a>
            <a href="/#pricing">Licensing &amp; pricing</a>
            <a href="/blog/">Blog</a>
            <a class="nav-cta" href="<?= h(REPOSITORY) ?>">GitHub <span aria-hidden="true">↗</span></a>
        </nav>
    </header>
<?php
}

function render_footer(): void
{
    ?>
    <footer class="site-footer">
        <a class="brand footer-brand" href="/"><span>WP<span>Sync</span></span></a>
        <p>Built for writing in your own editor and publishing to your own blog.</p>
        <p>© <?= h(date('Y')) ?> WPSync contributors // <a href="/#pricing">Licensing &amp; pricing</a> // <a href="https://pypi.org/project/wpsync/">Latest release on PyPI ↗</a></p>
        <p class="footer-note">WordPress is a trademark of the WordPress Foundation. WPSync is an independent project, not affiliated with or endorsed by the WordPress Foundation or Automattic.</p>
    </footer>
<?php
}
