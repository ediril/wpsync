<?php
declare(strict_types=1);

$repository = 'https://github.com/ediril/wpsync';
$year = (int) date('Y');
$title = 'WPSync — your WordPress blog, as Markdown files';
$description = 'Pull your WordPress posts into a folder, write in Obsidian or VS Code, preview the diff, then push exactly what you changed.';
$requestHost = (string) ($_SERVER['HTTP_HOST'] ?? '');
$validHost = preg_match('/\A[a-z0-9.-]+(?::[0-9]+)?\z/i', $requestHost) === 1;
$forwardedProtocol = strtolower((string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? ''));
$secureRequest = (
    strtolower((string) ($_SERVER['HTTPS'] ?? '')) === 'on'
    || $forwardedProtocol === 'https'
);
$requestPath = parse_url((string) ($_SERVER['REQUEST_URI'] ?? '/'), PHP_URL_PATH);
$pagePath = is_string($requestPath) && str_starts_with($requestPath, '/')
    ? $requestPath
    : '/';
$origin = $validHost
    ? ($secureRequest ? 'https://' : 'http://') . $requestHost
    : null;
$canonicalUrl = $origin === null ? null : $origin . $pagePath;
$socialImageUrl = $origin === null
    ? null
    : $origin . '/assets/social-preview.jpg';
$structuredData = [
    '@context' => 'https://schema.org',
    '@type' => 'SoftwareApplication',
    'name' => 'WPSync',
    'description' => $description,
    'applicationCategory' => 'DeveloperApplication',
    'operatingSystem' => 'Any operating system with Python 3.11+',
    'url' => $canonicalUrl ?? $repository,
    'downloadUrl' => 'https://pypi.org/project/wpsync/',
    'sameAs' => $repository,
    'license' => $repository . '/blob/main/LICENSE',
    'offers' => [
        [
            '@type' => 'Offer',
            'name' => 'PolyForm Strict license',
            'description' => 'No charge for uses permitted by PolyForm Strict 1.0.0. Listed personal uses must have no anticipated commercial application. The license also permits use by listed organizations. No rights to modify, redistribute, or create works based on WPSync are granted.',
            'price' => '0',
            'priceCurrency' => 'USD',
            'url' => $repository . '/blob/main/LICENSE',
        ],
        [
            '@type' => 'Offer',
            'name' => 'Commercial license',
            'description' => 'Commercial use outside the permissions of PolyForm Strict 1.0.0 requires a separate paid agreement before use. Contact emrah@diril.org for pricing.',
            'url' => ($canonicalUrl ?? $repository) . '#pricing',
        ],
    ],
];
if ($socialImageUrl !== null) {
    $structuredData['image'] = $socialImageUrl;
}
$structuredDataJson = json_encode(
    $structuredData,
    JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
        | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
);
if ($structuredDataJson === false) {
    throw new RuntimeException('Could not encode website structured data.');
}

function h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
?>
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#080b10">
    <meta name="description" content="<?= h($description) ?>">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="author" content="WPSync contributors">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="en_US">
    <meta property="og:site_name" content="WPSync">
    <meta property="og:title" content="<?= h($title) ?>">
    <meta property="og:description" content="<?= h($description) ?>">
<?php if ($canonicalUrl !== null && $socialImageUrl !== null): ?>
    <link rel="canonical" href="<?= h($canonicalUrl) ?>">
    <meta property="og:url" content="<?= h($canonicalUrl) ?>">
    <meta property="og:image" content="<?= h($socialImageUrl) ?>">
<?php if ($secureRequest): ?>
    <meta property="og:image:secure_url" content="<?= h($socialImageUrl) ?>">
<?php endif; ?>
<?php endif; ?>
    <meta property="og:image:type" content="image/jpeg">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="WPSync terminal session: pull posts, diff, then push to WordPress.">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="<?= h($title) ?>">
    <meta name="twitter:description" content="<?= h($description) ?>">
<?php if ($socialImageUrl !== null): ?>
    <meta name="twitter:image" content="<?= h($socialImageUrl) ?>">
    <meta name="twitter:image:alt" content="WPSync terminal session: pull posts, diff, then push to WordPress.">
<?php endif; ?>
    <script type="application/ld+json"><?= $structuredDataJson ?></script>
    <title><?= h($title) ?></title>
    <link rel="describedby" href="/llms.txt" type="text/markdown">
    <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
    <link rel="icon" href="assets/favicon-32x32.png" type="image/png" sizes="32x32">
    <link rel="shortcut icon" href="favicon.ico">
    <link rel="apple-touch-icon" href="assets/apple-touch-icon.png" sizes="180x180">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&amp;family=Space+Mono:wght@400;700&amp;display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/site.css">
    <script src="assets/site.js" defer></script>
</head>
<body>
    <a class="skip-link" href="#main">Skip to content</a>

    <header class="site-header" data-header>
        <a class="brand" href="#top" aria-label="WPSync home">
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
            <a href="#workflow">Workflow</a>
            <a href="#principles">Safety</a>
            <a href="#pricing">Licensing &amp; pricing</a>
            <a class="nav-cta" href="<?= h($repository) ?>">GitHub <span aria-hidden="true">↗</span></a>
        </nav>
    </header>

    <main id="main">
        <section class="hero" id="top">
            <div class="hero-copy">
                <p class="eyebrow"><span class="signal"></span> PRE-ALPHA</p>
                <h1>Your blog,<br><span>as Markdown files.</span></h1>
                <p class="hero-lede">
                    Pull your WordPress posts into a folder. Write in Obsidian or
                    VS Code. Preview the diff, then push exactly what you changed.
                </p>

                <div class="hero-actions">
                    <div class="install-command" aria-label="Installation command">
                        <span aria-hidden="true">$</span>
                        <code>uv tool install wpsync</code>
                        <button type="button" data-copy="uv tool install wpsync">
                            <span data-copy-label>copy</span>
                        </button>
                    </div>
                    <a class="text-link" href="#workflow">See the workflow <span aria-hidden="true">↓</span></a>
                </div>

                <div class="hero-meta" aria-label="Project metadata">
                    <div><span class="meta-label">platform</span><span class="meta-value">WordPress REST API</span></div>
                    <div><span class="meta-label">runtime</span><span class="meta-value">Python 3.11+</span></div>
                    <div><span class="meta-label">license</span><span class="meta-value">PolyForm Strict</span></div>
                </div>
            </div>

            <div class="terminal-wrap" aria-label="Example WPSync terminal session">
                <div class="terminal-glow"></div>
                <div class="terminal">
                    <div class="terminal-bar">
                        <div class="terminal-dots" aria-hidden="true"><i></i><i></i><i></i></div>
                        <span>~/blog — wpsync</span>
                        <span class="terminal-state">HTTPS</span>
                    </div>
                    <div class="terminal-body">
                        <p><span class="prompt">❯</span> <b>wpsync pull</b></p>
                        <p class="muted">Signed in to https://example.com as 'emrah' (administrator).</p>
                        <p><span class="added">+</span> &nbsp;123 &nbsp;content/hello-world.md &nbsp;<span class="muted">2 images</span></p>
                        <p><span class="changed">~</span> &nbsp;145 &nbsp;content/release-notes.md</p>
                        <p class="success">Pulled 2 posts (1 new, 1 updated), 2 images.</p>
                        <p class="terminal-gap"><span class="prompt">❯</span> <b>wpsync diff</b></p>
                        <p><span class="added">+ l</span> &nbsp; &nbsp;- &nbsp;content/drafts/idea.md &nbsp;<span class="muted">new post</span></p>
                        <p><span class="changed">~ l</span> &nbsp;145 &nbsp;content/release-notes.md &nbsp;<span class="muted">content</span></p>
                        <p class="terminal-gap"><span class="prompt">❯</span> <b>wpsync push</b></p>
                        <p><span class="added">+</span> &nbsp;170 &nbsp;content/drafts/idea.md &nbsp;<span class="muted">https://example.com/idea/</span></p>
                        <p><span class="changed">~</span> &nbsp;145 &nbsp;content/release-notes.md</p>
                        <p class="success">Pushed 2 posts (1 new, 1 updated).</p>
                        <span class="cursor" aria-hidden="true"></span>
                    </div>
                </div>
                <span class="coordinate coordinate-a">CONTENT/*.MD</span>
                <span class="coordinate coordinate-b">SYNC_CHANNEL_02</span>
            </div>
        </section>

        <section class="ticker" aria-label="Product attributes">
            <div>
                <span>PULL POSTS</span><i>◆</i><span>WRITE MARKDOWN</span><i>◆</i>
                <span>DIFF FIRST</span><i>◆</i><span>PUSH EXACTLY</span><i>◆</i>
                <span>PULL POSTS</span><i>◆</i><span>WRITE MARKDOWN</span><i>◆</i>
            </div>
        </section>

        <section class="section workflow" id="workflow">
            <div class="section-heading">
                <p class="eyebrow">01 // THE LOOP</p>
                <h2>Pull it. Write it. Push it.</h2>
                <p>WPSync maps a folder to your blog, keeps every post as a Markdown file, and shows what will change before anything reaches WordPress.</p>
            </div>

            <ol class="workflow-grid">
                <li>
                    <span class="step-number">01</span>
                    <div class="step-icon" aria-hidden="true">⌖</div>
                    <h3>Map the blog</h3>
                    <p>Connect a folder to your blog. WPSync signs in with an Application Password read from an environment variable and never stores it.</p>
                    <code>wpsync init myblog --site …</code>
                </li>
                <li>
                    <span class="step-number">02</span>
                    <div class="step-icon" aria-hidden="true">↧</div>
                    <h3>Pull your posts</h3>
                    <p>Every post becomes a Markdown file under <code>content/</code> with a YAML header for its title, slug, date, status, categories, and tags.</p>
                    <code>wpsync pull</code>
                </li>
                <li>
                    <span class="step-number">03</span>
                    <div class="step-icon" aria-hidden="true">✎</div>
                    <h3>Write in your editor</h3>
                    <p>Start a post from a file name and open it in Obsidian or VS Code. The title and slug can wait until you know them.</p>
                    <code>wpsync create idea</code>
                </li>
                <li>
                    <span class="step-number">04</span>
                    <div class="step-icon" aria-hidden="true">↥</div>
                    <h3>Diff, then push</h3>
                    <p>See exactly what push would change, then send it. Push updates only the part of a post you edited: the header, the content, or both.</p>
                    <code>wpsync push</code>
                </li>
            </ol>
        </section>

        <section class="section principles" id="principles">
            <div class="section-heading split-heading">
                <div>
                    <p class="eyebrow">02 // DESIGN SIGNAL</p>
                    <h2>Write anywhere.<br>Publish on purpose.</h2>
                </div>
                <p>WordPress stays responsible for your theme, comments, and public addresses. WPSync adds a local copy you control and a preview of every change.</p>
            </div>

            <div class="principle-grid">
                <article class="principle principle-wide">
                    <span class="principle-index">A</span>
                    <div>
                        <h3>Your files are the source of truth</h3>
                        <p>Posts are plain Markdown you can keep in Git and edit offline. Diff reads them without contacting the blog unless something changed.</p>
                    </div>
                    <div class="mini-diff" aria-hidden="true">
                        <span class="added">+ l</span><i></i><b>new post / created</b>
                        <span class="changed">~ l</span><i></i><b>changed / updated</b>
                        <span class="conflict">?</span><i></i><b>conflict / asks first</b>
                        <span class="removed">- l</span><i></i><b>deleted / with -p</b>
                    </div>
                </article>
                <article class="principle">
                    <span class="principle-index">B</span>
                    <h3>Nothing is overwritten silently</h3>
                    <p>Pull asks before replacing a file you edited. Push asks before replacing a post that also changed on WordPress. Every question defaults to no.</p>
                </article>
                <article class="principle">
                    <span class="principle-index">C</span>
                    <h3>Private until you say so</h3>
                    <p>New posts are private, so nothing is published until you set <code>status: public</code>. A future date schedules the post.</p>
                </article>
                <article class="principle">
                    <span class="principle-index">D</span>
                    <h3>Images that preview</h3>
                    <p>Image paths are relative to each post, so Obsidian and VS Code show them. Push uploads a new image to the media library once.</p>
                </article>
                <article class="principle principle-accent">
                    <span class="principle-index">E</span>
                    <h3>Deletion you can undo</h3>
                    <p>Push deletes nothing unless you add <code>-p</code>. A deleted post and its images are kept in <code>.trash/</code>, and <code>restore</code> brings them back.</p>
                </article>
            </div>
        </section>

        <section class="section pricing" id="pricing" aria-labelledby="pricing-title">
            <div class="section-heading">
                <p class="eyebrow">03 // LICENSING &amp; PRICING</p>
                <h2 id="pricing-title">Use under PolyForm Strict.<br>Commercial licensing available.</h2>
                <p>PolyForm Strict 1.0.0 defines the uses available at no charge. Commercial use outside those permissions requires a separate paid agreement.</p>
            </div>

            <div class="pricing-grid">
                <article class="license-card" aria-labelledby="noncommercial-title">
                    <p class="license-label">POLYFORM STRICT 1.0.0</p>
                    <h3 id="noncommercial-title">Free</h3>
                    <p class="license-description">No charge for uses permitted by the license:</p>
                    <ul class="license-features">
                        <li>Any noncommercial purpose</li>
                        <li>Listed personal uses, such as study and hobby projects, without any anticipated commercial application</li>
                        <li>Use by the organizations listed in the license</li>
                        <li>No rights to modify, redistribute, or create works based on WPSync are granted</li>
                    </ul>
                    <a class="text-link" href="<?= h($repository) ?>/blob/main/LICENSE">Read the free license <span aria-hidden="true">↗</span></a>
                </article>

                <article class="license-card license-card-commercial" aria-labelledby="commercial-title">
                    <p class="license-label">COMMERCIAL</p>
                    <h3 id="commercial-title">Contact for pricing</h3>
                    <p class="license-description">For commercial use outside the free license's permissions, including:</p>
                    <ul class="license-features">
                        <li>Internal business deployments</li>
                        <li>Client work and paid services</li>
                        <li>Commercial products and hosted services</li>
                    </ul>
                    <a class="button-primary" href="mailto:emrah@diril.org?subject=WPSync%20commercial%20license">Request a commercial license <span aria-hidden="true">↗</span></a>
                    <p class="license-agreement">A separate paid agreement is required before commercial use outside the free license's permissions.</p>
                </article>
            </div>

            <p class="licensing-note">PolyForm Strict expressly permits use by listed organizations, such as charitable organizations, educational institutions, and government institutions, regardless of funding source or obligations resulting from funding. The <a href="<?= h($repository) ?>/blob/main/LICENSE">full license</a> governs; this summary grants no additional permissions. Unsure which applies? <a href="mailto:emrah@diril.org?subject=WPSync%20licensing%20question">Ask Emrah Diril</a>.</p>
        </section>
    </main>

    <footer class="site-footer">
        <a class="brand footer-brand" href="#top"><span>WP<span>Sync</span></span></a>
        <p>Built for writing in your own editor and publishing to your own blog.</p>
        <p>© <?= h((string) $year) ?> WPSync contributors // <a href="#pricing">Licensing &amp; pricing</a> // <a href="https://pypi.org/project/wpsync/">Latest release on PyPI ↗</a></p>
        <p class="footer-note">WordPress is a trademark of the WordPress Foundation. WPSync is an independent project, not affiliated with or endorsed by the WordPress Foundation or Automattic.</p>
    </footer>
</body>
</html>
