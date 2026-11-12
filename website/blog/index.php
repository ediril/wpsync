<?php
declare(strict_types=1);

require dirname(__DIR__) . '/site.php';
require dirname(__DIR__) . '/vendor/autoload.php';

use League\CommonMark\Extension\FrontMatter\Data\SymfonyYamlFrontMatterParser;
use League\CommonMark\Extension\FrontMatter\FrontMatterParser;
use League\CommonMark\GithubFlavoredMarkdownConverter;

const POSTS_DIR = __DIR__ . '/posts';

/**
 * A post file: posts/<slug>.md with a YAML header holding title, date, and description.
 *
 * @return array{slug: string, title: string, date: DateTimeImmutable, description: string, markdown: string}
 */
function read_post(string $file): array
{
    $input = (new FrontMatterParser(new SymfonyYamlFrontMatterParser()))
        ->parse((string) file_get_contents($file));
    $header = $input->getFrontMatter();
    $name = basename($file);
    if (!is_array($header) || !is_string($header['title'] ?? null) || !is_string($header['description'] ?? null)) {
        throw new RuntimeException("$name needs a title and a description in its header");
    }
    // YAML reads an unquoted date as a UTC timestamp.
    $date = $header['date'] ?? null;
    $date = match (true) {
        is_int($date) => (new DateTimeImmutable('@' . $date))->setTime(0, 0),
        is_string($date) => DateTimeImmutable::createFromFormat('!Y-m-d', $date),
        default => false,
    };
    if ($date === false) {
        throw new RuntimeException("$name needs a date in the form YYYY-MM-DD");
    }
    return [
        'slug' => basename($file, '.md'),
        'title' => $header['title'],
        'date' => $date,
        'description' => $header['description'],
        'markdown' => $input->getContent(),
    ];
}

/** @return list<array{slug: string, title: string, date: DateTimeImmutable, description: string, markdown: string}> */
function all_posts(): array
{
    $posts = array_map(read_post(...), glob(POSTS_DIR . '/*.md') ?: []);
    usort($posts, fn (array $a, array $b) => [$b['date'], $b['slug']] <=> [$a['date'], $a['slug']]);
    return $posts;
}

function render_date(DateTimeImmutable $date): string
{
    return '<time datetime="' . $date->format('Y-m-d') . '">' . $date->format('M j, Y') . '</time>';
}

function blog_page(array $page, callable $body): void
{
    render_head($page);
    echo "<body>\n";
    render_header();
    echo "\n    <main id=\"main\" class=\"blog\">\n";
    $body();
    echo "    </main>\n\n";
    render_footer();
    echo "</body>\n</html>\n";
}

$path = rtrim(request_path(), '/');

if ($path === '/blog') {
    $posts = all_posts();
    blog_page(
        [
            'title' => 'Blog — WPSync',
            'description' => 'Notes on WPSync: writing a WordPress blog as Markdown files.',
            'type' => 'website',
            'structured_data' => [
                '@context' => 'https://schema.org',
                '@type' => 'Blog',
                'name' => 'WPSync blog',
            ],
        ],
        function () use ($posts): void {
            ?>
        <section class="section blog-index">
            <div class="section-heading">
                <p class="eyebrow">BLOG</p>
                <h2>Notes from the folder.</h2>
            </div>
            <ol class="post-list">
<?php foreach ($posts as $post): ?>
                <li>
                    <?= render_date($post['date']) ?>

                    <h3><a href="/blog/<?= h($post['slug']) ?>"><?= h($post['title']) ?></a></h3>
                    <p><?= h($post['description']) ?></p>
                </li>
<?php endforeach; ?>
            </ol>
        </section>
<?php
        },
    );
    return;
}

$file = preg_match('#\A/blog/([a-z0-9-]+)\z#', $path, $match) === 1
    ? POSTS_DIR . '/' . $match[1] . '.md'
    : null;
if ($file === null || !is_file($file)) {
    http_response_code(404);
    blog_page(
        [
            'title' => 'Not found — WPSync',
            'description' => 'There is no blog post at this address.',
            'type' => 'website',
            'structured_data' => ['@context' => 'https://schema.org', '@type' => 'WebPage'],
        ],
        function (): void {
            ?>
        <section class="section blog-index">
            <div class="section-heading">
                <p class="eyebrow">404</p>
                <h2>No post here.</h2>
                <p>See <a class="text-link" href="/blog/">all posts</a>.</p>
            </div>
        </section>
<?php
        },
    );
    return;
}

$post = read_post($file);
$html = (new GithubFlavoredMarkdownConverter())->convert($post['markdown']);
blog_page(
    [
        'title' => $post['title'] . ' — WPSync',
        'description' => $post['description'],
        'type' => 'article',
        'structured_data' => [
            '@context' => 'https://schema.org',
            '@type' => 'BlogPosting',
            'headline' => $post['title'],
            'description' => $post['description'],
            'datePublished' => $post['date']->format('Y-m-d'),
            'author' => ['@type' => 'Person', 'name' => 'Emrah Diril'],
        ],
    ],
    function () use ($post, $html): void {
        ?>
        <article class="section post">
            <header class="post-header">
                <p class="eyebrow"><a href="/blog/">BLOG</a> // <?= render_date($post['date']) ?></p>
                <h1><?= h($post['title']) ?></h1>
            </header>
            <div class="prose">
<?= $html ?>
            </div>
        </article>
<?php
    },
);
