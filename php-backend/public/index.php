<?php

declare(strict_types=1);

use App\Controllers\ApiController;
use App\Controllers\PagesController;
use App\HttpError;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Slim\Factory\AppFactory;

require dirname(__DIR__) . '/vendor/autoload.php';

// PHP 内建服务器：静态文件直接放行
if (PHP_SAPI === 'cli-server') {
    $path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
    $file = __DIR__ . $path;
    if ($path !== '/' && is_file($file)) {
        return false;
    }
}

$app = AppFactory::create();
$app->addBodyParsingMiddleware();
$app->addRoutingMiddleware();

// 与 FastAPI 一致的错误输出：{"detail": "..."}
$errorMiddleware = $app->addErrorMiddleware(true, true, true);
$errorMiddleware->setDefaultErrorHandler(function (
    ServerRequestInterface $request,
    Throwable $exception
) use ($app): ResponseInterface {
    $response = $app->getResponseFactory()->createResponse();
    if ($exception instanceof HttpError) {
        $response->getBody()->write(json_encode(['detail' => $exception->detail], JSON_UNESCAPED_UNICODE));
        return $response->withHeader('Content-Type', 'application/json; charset=utf-8')->withStatus($exception->status);
    }
    if ($exception instanceof \Slim\Exception\HttpNotFoundException) {
        $response->getBody()->write(json_encode(['detail' => 'Not Found'], JSON_UNESCAPED_UNICODE));
        return $response->withHeader('Content-Type', 'application/json; charset=utf-8')->withStatus(404);
    }
    if ($exception instanceof \Slim\Exception\HttpMethodNotAllowedException) {
        $response->getBody()->write(json_encode(['detail' => 'Method Not Allowed'], JSON_UNESCAPED_UNICODE));
        return $response->withHeader('Content-Type', 'application/json; charset=utf-8')->withStatus(405);
    }
    $detail = $exception->getMessage();
    $response->getBody()->write(json_encode(['detail' => $detail], JSON_UNESCAPED_UNICODE));
    return $response->withHeader('Content-Type', 'application/json; charset=utf-8')->withStatus(500);
});

$pages = new PagesController();
$api = new ApiController();

// ---------- 页面路由（routers/pages.py 对等） ----------
$app->post('/demo/switch-account', [$pages, 'switchAccount']);
$app->post('/demo/switch-store', [$pages, 'switchStore']);
$app->get('/', [$pages, 'dashboard']);
$app->get('/templates', [$pages, 'templatesRedirect']);
$app->get('/templates/{template_id:[0-9]+}', [$pages, 'templatesRedirect']);
$app->post('/templates/{template_id:[0-9]+}/test', [$pages, 'testTemplate']);
$app->post('/templates/{template_id:[0-9]+}/publish', [$pages, 'publishTemplate']);
$app->post('/templates/{template_id:[0-9]+}/unpublish', [$pages, 'unpublishTemplate']);
$app->get('/mappings', [$pages, 'mappings']);
$app->get('/logs', [$pages, 'logs']);
$app->get('/reports', [$pages, 'reports']);
$app->get('/reports/{run_id:[0-9]+}', [$pages, 'reportDetail']);
$app->get('/daily', [$pages, 'daily']);
$app->post('/daily/generate', [$pages, 'dailyGenerate']);
$app->get('/daily/review-template', [$pages, 'dailyReviewTemplate']);
$app->get('/daily/review-logistics-template', [$pages, 'dailyReviewLogisticsTemplate']);
$app->get('/daily/sample-template', [$pages, 'dailySampleTemplate']);
$app->get('/daily/{run_id:[0-9]+}/export-sku', [$pages, 'dailyExportSku']);
$app->get('/daily/{run_id:[0-9]+}/export', [$pages, 'dailyExport']);
$app->get('/imports', [$pages, 'importsRedirect']);

// ---------- API 路由（routers/api.py 对等） ----------
$app->post('/api/import', [$api, 'importExcel']);
$app->post('/api/generate', [$api, 'generate']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/report-lines', [$api, 'listReportLines']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/mapped-fields', [$api, 'mappedFields']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/catalog', [$api, 'catalogTree']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/schema', [$api, 'schema']);
$app->get('/api/mappings/{mapping_id:[0-9]+}', [$api, 'getMapping']);
$app->put('/api/mappings/{mapping_id:[0-9]+}', [$api, 'saveMapping']);
$app->post('/api/mappings', [$api, 'createMapping']);
$app->post('/api/formula-lines', [$api, 'createFormulaLine']);
$app->put('/api/formula-lines/{mapping_id:[0-9]+}', [$api, 'saveFormulaLine']);
$app->delete('/api/mappings/{mapping_id:[0-9]+}', [$api, 'deleteMapping']);
$app->post('/api/data-sources/{data_source_id:[0-9]+}/report-fields', [$api, 'quickAddReportField']);
$app->put('/api/data-sources/{data_source_id:[0-9]+}/report-fields/order', [$api, 'reorderReportFields']);
$app->patch('/api/mappings/{mapping_id:[0-9]+}/label', [$api, 'patchMappingLabel']);
$app->patch('/api/report-runs/{run_id:[0-9]+}/values/{value_id:[0-9]+}', [$api, 'patchReportValue']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/settings', [$api, 'getDataSourceSettings']);
$app->put('/api/data-sources/{data_source_id:[0-9]+}/settings', [$api, 'updateDataSourceSettings']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/config/export', [$api, 'exportDataSourceConfig']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/review-orders/template', [$api, 'downloadReviewTemplate']);
$app->post('/api/data-sources/{data_source_id:[0-9]+}/review-orders/import', [$api, 'importReviewOrders']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/review-logistics/template', [$api, 'downloadReviewLogisticsTemplate']);
$app->post('/api/data-sources/{data_source_id:[0-9]+}/review-logistics/import', [$api, 'importReviewLogistics']);
$app->get('/api/data-sources/{data_source_id:[0-9]+}/sample-orders/template', [$api, 'downloadSampleTemplate']);
$app->post('/api/data-sources/{data_source_id:[0-9]+}/sample-orders/import', [$api, 'importSampleOrders']);

$app->run();
