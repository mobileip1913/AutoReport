<?php

declare(strict_types=1);

namespace App;

use App\Services\Timezone;
use Twig\Environment;
use Twig\Loader\FilesystemLoader;
use Twig\TwigFilter;

/**
 * Twig 模板环境（对应 Python 版 Jinja2Templates）。
 */
final class Views
{
    private static ?Environment $twig = null;

    public static function twig(): Environment
    {
        if (self::$twig !== null) {
            return self::$twig;
        }
        $loader = new FilesystemLoader(Config::rootDir() . '/templates');
        $twig = new Environment($loader, [
            'cache' => false,
            'autoescape' => 'html',
        ]);
        $twig->addFilter(new TwigFilter('cst', fn(?string $v, string $fmt = 'Y-m-d H:i') => Timezone::toCst($v, $fmt)));
        self::$twig = $twig;
        return $twig;
    }

    public static function render(string $name, array $context = []): string
    {
        return self::twig()->render($name, $context);
    }
}
