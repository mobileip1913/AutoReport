<?php

declare(strict_types=1);

namespace App;

/**
 * 与 FastAPI HTTPException 对等：状态码 + detail（JSON 输出为 {"detail": "..."}）。
 */
class HttpError extends \Exception
{
    public function __construct(
        public readonly int $status,
        public readonly string $detail,
    ) {
        parent::__construct($detail, $status);
    }
}
