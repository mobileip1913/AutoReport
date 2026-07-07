<?php

declare(strict_types=1);

namespace App\Services;

/**
 * 公式解析与求值，与 Python 版 services/formula.py 对等。
 * 仅支持 + - * / 与一元负号、括号、数字字面量。
 */
final class Formula
{
    public const FIELD_PATTERN = '/\{field:([a-zA-Z0-9_]+)\}/';

    /** @return string[] */
    public static function extractFieldCodes(string $expression): array
    {
        preg_match_all(self::FIELD_PATTERN, $expression, $m);
        return $m[1];
    }

    /**
     * 将 ={field:a}+{field:b}-{field:c} 转为取数 parts（复用字段 + 加减）。
     * @return array<int, array{0:string,1:string}>|null [code, combine_op][]
     */
    public static function expressionToRefParts(string $expression): ?array
    {
        $expr = trim($expression);
        if (!str_starts_with($expr, '=')) {
            return null;
        }
        $body = str_replace(' ', '', substr($expr, 1));
        preg_match_all('/([+-]?)\{field:([a-zA-Z0-9_]+)\}/', $body, $matches, PREG_SET_ORDER);
        if (!$matches) {
            return null;
        }
        $parts = [];
        foreach ($matches as $mt) {
            $combine = $mt[1] === '-' ? 'subtract' : 'add';
            $parts[] = [$mt[2], $combine];
        }
        return $parts;
    }

    /** @param array<string, float> $fieldValues */
    private static function resolveFields(string $expression, array $fieldValues): string
    {
        return preg_replace_callback(self::FIELD_PATTERN, function ($match) use ($fieldValues) {
            $code = $match[1];
            if (!array_key_exists($code, $fieldValues)) {
                throw new FormulaError("字段 {$code} 无可用数据");
            }
            return self::floatToStr((float) $fieldValues[$code]);
        }, $expression);
    }

    private static function floatToStr(float $v): string
    {
        // 避免科学计数法进入表达式
        $s = sprintf('%.12F', $v);
        return rtrim(rtrim($s, '0'), '.') ?: '0';
    }

    /** @param array<string, float> $fieldValues */
    public static function evaluateExpression(string $expression, array $fieldValues): float
    {
        $expr = trim($expression);
        if (str_starts_with($expr, '=')) {
            $expr = trim(substr($expr, 1));
        }
        if (preg_match('/^\{field:([a-zA-Z0-9_]+)\}$/', $expr, $m)) {
            $code = $m[1];
            if (!array_key_exists($code, $fieldValues)) {
                throw new FormulaError("字段 {$code} 无可用数据");
            }
            return (float) $fieldValues[$code];
        }
        $resolved = self::resolveFields($expr, $fieldValues);
        if (preg_match('/[a-zA-Z_]/', $resolved)) {
            throw new FormulaError("公式中存在未解析字段: {$resolved}");
        }
        $parser = new ArithmeticParser($resolved);
        $value = $parser->parse();
        return $value;
    }

    public static function formatValue(?float $value, string $formatType): string
    {
        if ($value === null) {
            return '-';
        }
        return match ($formatType) {
            'currency' => '¥' . number_format($value, 2),
            'usd' => '$' . number_format($value, 2),
            'percent' => sprintf('%.2f%%', $value * 100),
            'integer' => number_format((float) round($value), 0),
            default => number_format($value, 2),
        };
    }
}

/**
 * 递归下降算术解析器：expr := term (('+'|'-') term)*; term := factor (('*'|'/') factor)*;
 * factor := ('-'|'+')* (number | '(' expr ')')
 */
final class ArithmeticParser
{
    private string $s;
    private int $pos = 0;
    private int $len;

    public function __construct(string $input)
    {
        $this->s = $input;
        $this->len = strlen($input);
    }

    public function parse(): float
    {
        $v = $this->parseExpr();
        $this->skipWs();
        if ($this->pos < $this->len) {
            throw new FormulaError('不支持的公式语法');
        }
        return $v;
    }

    private function skipWs(): void
    {
        while ($this->pos < $this->len && ctype_space($this->s[$this->pos])) {
            $this->pos++;
        }
    }

    private function peek(): ?string
    {
        $this->skipWs();
        return $this->pos < $this->len ? $this->s[$this->pos] : null;
    }

    private function parseExpr(): float
    {
        $v = $this->parseTerm();
        while (($c = $this->peek()) === '+' || $c === '-') {
            $this->pos++;
            $rhs = $this->parseTerm();
            $v = $c === '+' ? $v + $rhs : $v - $rhs;
        }
        return $v;
    }

    private function parseTerm(): float
    {
        $v = $this->parseFactor();
        while (($c = $this->peek()) === '*' || $c === '/') {
            $this->pos++;
            $rhs = $this->parseFactor();
            if ($c === '/') {
                if ($rhs == 0.0) {
                    throw new FormulaError('除数不能为 0');
                }
                $v /= $rhs;
            } else {
                $v *= $rhs;
            }
        }
        return $v;
    }

    private function parseFactor(): float
    {
        $c = $this->peek();
        if ($c === '-') {
            $this->pos++;
            return -$this->parseFactor();
        }
        if ($c === '+') {
            $this->pos++;
            return $this->parseFactor();
        }
        if ($c === '(') {
            $this->pos++;
            $v = $this->parseExpr();
            if ($this->peek() !== ')') {
                throw new FormulaError('不支持的公式语法');
            }
            $this->pos++;
            return $v;
        }
        $this->skipWs();
        if (!preg_match('/\G\d+(\.\d+)?([eE][+-]?\d+)?/', $this->s, $m, 0, $this->pos)) {
            throw new FormulaError('不支持的公式语法');
        }
        $this->pos += strlen($m[0]);
        return (float) $m[0];
    }
}
