document.addEventListener('DOMContentLoaded', function() {
const canvas = document.getElementById('gameCanvas');
if (!canvas) return; // Защита от ошибок если канвас не найден

const ctx = canvas.getContext('2d');
const startScreen = document.getElementById('startScreen');
const startButton = document.getElementById('startButton');

// Set canvas size for 15x15 grid
const CELL_SIZE = 32;
const GRID_WIDTH = 15;
const GRID_HEIGHT = 15;
canvas.width = CELL_SIZE * GRID_WIDTH;
canvas.height = CELL_SIZE * GRID_HEIGHT;

// Game state
let gameStarted = false;
let gamePaused = false;
let score = 0;
let lives = 3;
let animationFrame = 0;
let gameOverTimeout = null;

// Rabbit properties (центр лабиринта)
const rabbit = {
    x: 7 * CELL_SIZE,
    y: 11 * CELL_SIZE,
    direction: 'right',
    nextDirection: 'right',
    speed: 2,
    size: CELL_SIZE - 2
};

// Wolves (enemies) properties
const wolves = [
    { x: 6 * CELL_SIZE, y: 5 * CELL_SIZE, direction: 'right', speed: 1.5, state: 'patrol', patrolPath: [], patrolIndex: 0 },
    { x: 8 * CELL_SIZE, y: 5 * CELL_SIZE, direction: 'left', speed: 1.5, state: 'patrol', patrolPath: [], patrolIndex: 0 },
    { x: 6 * CELL_SIZE, y: 6 * CELL_SIZE, direction: 'up', speed: 1.5, state: 'patrol', patrolPath: [], patrolIndex: 0 },
    { x: 8 * CELL_SIZE, y: 6 * CELL_SIZE, direction: 'down', speed: 1.5, state: 'patrol', patrolPath: [], patrolIndex: 0 }
];

// Maze layout (1 - wall, 0 - path)
const maze = [
  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
  [1,0,0,0,1,0,0,0,0,0,1,0,0,0,1],
  [1,0,1,0,1,0,1,1,1,0,1,0,1,0,1],
  [1,0,1,0,0,0,0,1,0,0,0,0,1,0,1],
  [1,0,1,1,1,1,0,1,0,1,1,1,1,0,1],
  [1,0,0,0,0,1,0,0,0,1,0,0,0,0,1],
  [1,1,1,0,1,1,1,0,1,1,1,0,1,1,1],
  [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
  [1,1,1,0,1,1,1,0,1,1,1,0,1,1,1],
  [1,0,0,0,1,0,0,0,0,0,1,0,0,0,1],
  [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1],
  [1,0,0,0,0,0,1,0,1,0,0,0,0,0,1],
  [1,0,1,1,1,1,1,0,1,1,1,1,1,0,1],
  [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
  [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
];

// Carrots (food) properties
let carrots = [];
function resetCarrots() {
    carrots = [];
    for (let i = 0; i < GRID_WIDTH; i++) {
        for (let j = 0; j < GRID_HEIGHT; j++) {
            if (maze[j][i] === 0) {
                carrots.push({ x: i * CELL_SIZE, y: j * CELL_SIZE });
            }
        }
    }
}
resetCarrots();

// В начале файла добавим расширенное логирование
// Создаем отдельную переменную для логов, чтобы не засорять консоль
let DEBUG_LOGS = [];
let DEBUG_MODE = true;

function debugLog(tag, message, data) {
    if (!DEBUG_MODE) return;
    
    const log = {
        time: new Date().toISOString(),
        tag: tag,
        message: message,
        data: data
    };
    
    DEBUG_LOGS.push(log);
    
    // Ограничиваем размер массива логов
    if (DEBUG_LOGS.length > 1000) {
        DEBUG_LOGS.shift();
    }
    
    // Вывод в консоль с меткой времени
    console.log(`[DEBUG][${tag}] ${message}`, data || '');
}

// Функция для получения всех логов в виде строки
function getDumpLogs() {
    return JSON.stringify(DEBUG_LOGS, null, 2);
}

// Добавляем команду для вывода логов в консоль
window.dumpGameLogs = function() {
    console.log('====== GAME DEBUG LOGS ======');
    console.log(DEBUG_LOGS);
    console.log('============================');
    return 'Logs dumped to console';
};

// Функция для проверки целостности всех игровых объектов
function validateGameObjects() {
    console.log("Validating game objects...");

    // Проверяем кролика
    if (!rabbit) {
        console.error("Rabbit object is missing!");
        rabbit = {
            x: 7 * CELL_SIZE,
            y: 11 * CELL_SIZE,
            direction: 'right',
            nextDirection: 'right',
            speed: 2,
            size: CELL_SIZE - 2
        };
    }

    // Проверяем координаты кролика
    const rabbitGridX = Math.floor((rabbit.x + CELL_SIZE/2) / CELL_SIZE);
    const rabbitGridY = Math.floor((rabbit.y + CELL_SIZE/2) / CELL_SIZE);
    
    if (rabbitGridX < 0 || rabbitGridX >= GRID_WIDTH || rabbitGridY < 0 || rabbitGridY >= GRID_HEIGHT || maze[rabbitGridY][rabbitGridX] === 1) {
        console.error("Rabbit in invalid position:", rabbitGridX, rabbitGridY);
        rabbit.x = 7 * CELL_SIZE;
        rabbit.y = 11 * CELL_SIZE;
        centerInCell(rabbit);
    }

    // Проверяем волков
    if (!wolves || !Array.isArray(wolves)) {
        console.error("Wolves array is invalid!");
        wolves = [];
    }

    // Если волков нет, создаем их
    if (wolves.length === 0) {
        console.warn("No wolves found, creating default wolves");
        resetPositions();
    } else {
        // Проверяем каждого волка
        wolves.forEach((wolf, index) => {
            if (!wolf || typeof wolf !== 'object') {
                console.error(`Wolf ${index} is invalid!`);
                return;
            }

            // Проверяем координаты волка
            const wolfGridX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
            const wolfGridY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
            
            if (wolfGridX < 0 || wolfGridX >= GRID_WIDTH || wolfGridY < 0 || wolfGridY >= GRID_HEIGHT || maze[wolfGridY][wolfGridX] === 1) {
                console.error(`Wolf ${index} in invalid position:`, wolfGridX, wolfGridY);
                
                // Перемещаем волка в безопасное место
                const safePositions = [
                    {x: 1, y: 1}, 
                    {x: GRID_WIDTH-2, y: 1}, 
                    {x: 1, y: GRID_HEIGHT-2}, 
                    {x: GRID_WIDTH-2, y: GRID_HEIGHT-2}
                ];
                
                const safePos = safePositions[index % safePositions.length];
                wolf.x = safePos.x * CELL_SIZE;
                wolf.y = safePos.y * CELL_SIZE;
                centerInCell(wolf);
            }

            // Проверяем направление волка
            if (!wolf.direction || !['up', 'down', 'left', 'right'].includes(wolf.direction)) {
                console.error(`Wolf ${index} has invalid direction: ${wolf.direction}`);
                wolf.direction = ['right', 'left', 'up', 'down'][index % 4];
            }

            // Проверяем скорость волка
            if (!wolf.speed || wolf.speed <= 0) {
                console.error(`Wolf ${index} has invalid speed: ${wolf.speed}`);
                wolf.speed = 1.5;
            }
        });
    }

    // Проверяем морковки
    if (!carrots || !Array.isArray(carrots)) {
        console.error("Carrots array is invalid!");
        resetCarrots();
    } else if (carrots.length === 0) {
        console.warn("No carrots found, resetting them");
        resetCarrots();
    } else {
        // Проверяем каждую морковку
        const validCarrots = carrots.filter(carrot => {
            if (!carrot || typeof carrot !== 'object') return false;
            
            const carrotGridX = Math.floor((carrot.x + CELL_SIZE/2) / CELL_SIZE);
            const carrotGridY = Math.floor((carrot.y + CELL_SIZE/2) / CELL_SIZE);
            
            return !(carrotGridX < 0 || carrotGridX >= GRID_WIDTH || carrotGridY < 0 || carrotGridY >= GRID_HEIGHT || maze[carrotGridY][carrotGridX] === 1);
        });

        if (validCarrots.length !== carrots.length) {
            console.warn(`Removed ${carrots.length - validCarrots.length} invalid carrots`);
            carrots = validCarrots;
        }
    }

    console.log("Game objects validation complete");
    return true;
}

// Обновляем функцию initGameElements, добавляя проверку объектов
function initGameElements() {
    try {
        if (!ctx) {
            console.error("Canvas context is not available");
            return;
        }
        
        // Проверка структуры лабиринта
        if (!maze || !Array.isArray(maze)) {
            console.error("Maze is not defined or not an array!");
            // Создаём простой лабиринт как резервный вариант
            maze = [
              [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
              [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
              [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1],
              [1,0,1,0,0,0,0,0,0,0,0,0,1,0,1],
              [1,0,1,0,1,1,1,1,1,1,1,0,1,0,1],
              [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
              [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1],
              [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
              [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1],
              [1,0,1,0,0,0,0,0,0,0,0,0,1,0,1],
              [1,0,1,0,1,1,1,1,1,1,1,0,1,0,1],
              [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
              [1,0,1,1,1,1,1,1,1,1,1,1,1,0,1],
              [1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
              [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
            ];
            console.log("Created fallback maze");
        } else {
            // Проверяем размеры и структуру лабиринта
            for (let y = 0; y < maze.length; y++) {
                if (!Array.isArray(maze[y]) || maze[y].length !== GRID_WIDTH) {
                    console.error(`Invalid maze row ${y}: expected array with ${GRID_WIDTH} elements, got:`, maze[y]);
                    maze[y] = Array(GRID_WIDTH).fill(0);
                    maze[y][0] = 1; // Левая стена
                    maze[y][GRID_WIDTH-1] = 1; // Правая стена
                }
            }
            
            console.log("Maze validation complete, dimensions:", maze.length, "x", maze[0]?.length);
        }
        
        // Проверяем целостность игровых объектов
        validateGameObjects();
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawMaze();
        
        // Проверка корректности данных перед отрисовкой
        if (carrots && Array.isArray(carrots) && carrots.length > 0) {
            drawCarrots();
        } else {
            console.warn("No carrots to draw during initialization");
            resetCarrots();
        }
        
        // Проверка волков
        if (!wolves || !Array.isArray(wolves) || wolves.length === 0) {
            console.warn("No wolves found during initialization, resetting positions");
            resetPositions();
        } else {
            // Проверяем наличие патрульных маршрутов у волков
            wolves.forEach((wolf, index) => {
                if (!wolf.direction || wolf.direction === '') {
                    console.warn(`Wolf ${index} has no direction, generating one`);
                    wolf.direction = ['right', 'left', 'up', 'down'][index % 4];
                }
            });
            drawWolves();
        }
        
        drawRabbit();
        
        if (startScreen) {
            startScreen.style.display = 'flex';
            startScreen.style.opacity = '1';
        }
        
        console.log("Game elements initialized");
        debugLog('INIT', 'Game elements initialized', {
            carrots: carrots?.length || 0,
            wolves: wolves?.length || 0,
            rabbit: rabbit ? 'ready' : 'missing'
        });
    } catch (error) {
        console.error("Error in initGameElements:", error);
    }
}

// Обработка события инициализации игры
document.addEventListener('initGame', function() {
    resetPositions();
    resetCarrots();
    initGameElements();
});

// Обработка предзагрузки игры
document.addEventListener('preloadGame', function() {
    console.log('Preloading game elements');
    // Отрисовка всех элементов игры без показа игрового экрана
    try {
        if (!ctx) return;
        
        // Отрисовка за пределами видимости для предзагрузки ресурсов
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = CELL_SIZE * GRID_WIDTH;
        tempCanvas.height = CELL_SIZE * GRID_HEIGHT;
        const tempCtx = tempCanvas.getContext('2d');
        
        if (!tempCtx) return;
        
        // Отрисовка элементов игры на временный холст
        tempCtx.fillStyle = '#7ec850';
        tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
        
        // Отрисовка стен
        tempCtx.fillStyle = '#3e5c2c';
        tempCtx.strokeStyle = '#a5d6a7';
        tempCtx.lineWidth = 2;
        tempCtx.fillRect(0, 0, CELL_SIZE, CELL_SIZE);
        tempCtx.strokeRect(0, 0, CELL_SIZE, CELL_SIZE);
        
        // Отрисовка кролика
        tempCtx.fillStyle = '#fff';
        tempCtx.beginPath();
        tempCtx.arc(CELL_SIZE/2, CELL_SIZE/2, (CELL_SIZE-2)/2, 0, Math.PI * 2);
        tempCtx.fill();
        
        // Отрисовка волка
        tempCtx.fillStyle = '#888';
        tempCtx.beginPath();
        tempCtx.arc(CELL_SIZE/2, CELL_SIZE/2, (CELL_SIZE-4)/2, 0, Math.PI * 2);
        tempCtx.fill();
        
        // Отрисовка морковки
        tempCtx.fillStyle = '#ff9800';
        tempCtx.beginPath();
        tempCtx.ellipse(CELL_SIZE/2, CELL_SIZE/2, 6, 12, 0, 0, Math.PI * 2);
        tempCtx.fill();
        
        console.log('Game assets preloaded successfully');
        
        // После предзагрузки, проверяем начальную отрисовку
        setTimeout(initGameElements, 200);
        
    } catch(error) {
        console.error('Error in game preload:', error);
    }
});

// Listen for modal closing
document.addEventListener('gameModalClosed', function() {
    console.log("Game modal closed event received");
    gamePaused = true;
    gameStarted = false;
    if (startScreen) {
        startScreen.style.display = 'flex';
        setTimeout(() => startScreen.style.opacity = 1, 10);
    }
});

// Функция старта игры с расширенным логированием
function setupStartButton() {
    try {
        const startButton = document.getElementById('startButton');
        debugLog('INIT', 'Setting up start button', startButton ? 'Found' : 'Not found');
        
        if (!startButton) {
            console.warn('Start button not found, will try to search again later');
            // Попробуем найти кнопку позже
            setTimeout(setupStartButton, 500);
            return;
        }
        
        // Удалить все существующие обработчики
        const newBtn = startButton.cloneNode(true);
        if (startButton.parentNode) {
            startButton.parentNode.replaceChild(newBtn, startButton);
            debugLog('INIT', 'Replaced start button');
        } else {
            console.error('Start button has no parent node');
            document.body.appendChild(newBtn);
            debugLog('INIT', 'Appended new start button to body');
        }
        
        // Добавить новый обработчик
        newBtn.addEventListener('click', function(event) {
            debugLog('GAME', 'Start button clicked');
            event.preventDefault(); // Предотвращаем стандартное поведение кнопки
            
            if (!ctx) {
                console.error("Canvas context is not available");
                return;
            }
            
            gameStarted = true;
            gamePaused = false;
            
            if (startScreen) {
                startScreen.style.opacity = 0;
                setTimeout(() => {
                    startScreen.style.display = 'none';
                    debugLog('GAME', 'Start screen hidden');
                }, 400);
            } else {
                console.warn("Start screen not found");
            }
            
            try {
                debugLog('GAME', 'Resetting game state');
                // Проверка и инициализация лабиринта
                if (!maze || !Array.isArray(maze) || maze.length === 0) {
                    console.error("Maze is invalid, reinitializing");
                    initGameElements(); // Пересоздаем элементы игры
                }
                
                // Сначала сбрасываем позиции - ВАЖНО!
                resetPositions();
                resetCarrots();
                score = 0;
                lives = 3;
                animationFrame = 0;
                
                // Убедимся, что все волки имеют направления
                if (wolves && Array.isArray(wolves)) {
                    wolves.forEach((wolf, index) => {
                        if (!wolf.direction || wolf.direction === '') {
                            wolf.direction = ['right', 'left', 'up', 'down'][index % 4];
                            console.log(`Wolf ${index} initialized with direction: ${wolf.direction}`);
                        }
                    });
                } else {
                    console.error("Wolves array is invalid");
                    wolves = []; // Сбрасываем массив волков
                    resetPositions(); // Пересоздаем волков
                }
                
                // Проверяем состояние объектов
                debugLog('STATE', 'Rabbit', rabbit ? JSON.stringify(rabbit) : 'missing');
                debugLog('STATE', 'Wolves', wolves ? wolves.length : 'missing');
                debugLog('STATE', 'Carrots', carrots ? carrots.length : 'missing');
                
                // Принудительная отрисовка всех элементов
                debugLog('RENDER', 'Rendering initial state');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                drawMaze();
                if (carrots && carrots.length > 0) drawCarrots();
                if (wolves && wolves.length > 0) drawWolves();
                if (rabbit) drawRabbit();
                drawScore();
                
                // Запускаем игровой цикл с небольшой задержкой
                debugLog('GAME', 'Starting game loop');
                setTimeout(() => {
                    try {
                        gameLoop(true); // true для первого запуска
                    } catch (loopErr) {
                        console.error("Error starting game loop:", loopErr);
                        // Восстановление при ошибке
                        validateGameObjects();
                        gameLoop(true);
                    }
                }, 100);
            } catch (err) {
                debugLog('ERROR', 'Error during game start', err.toString());
                console.error("Game start error:", err);
            }
        });
        
        debugLog('INIT', 'Start button initialized successfully');
    } catch (setupErr) {
        console.error("Error in setupStartButton:", setupErr);
    }
}

function drawCarrots() {
    try {
        if (!carrots || !Array.isArray(carrots) || carrots.length === 0) {
            console.warn("No carrots to draw");
            return;
        }
        
        console.log("Drawing carrots:", carrots.length);
        
        // Рисуем морковки с анимацией (для gameStarted == true)
        if (gameStarted) {
            carrots.forEach((carrot, i) => {
                if (isNaN(carrot.x) || isNaN(carrot.y)) {
                    console.error("Invalid carrot position", carrot);
                    return;
                }
                
                // Тело морковки
                ctx.save();
                ctx.shadowColor = '#ff9800';
                ctx.shadowBlur = 8;
                ctx.fillStyle = '#ff9800';
                ctx.beginPath();
                ctx.ellipse(
                    carrot.x + CELL_SIZE/2,
                    carrot.y + CELL_SIZE/2 + 4,
                    6, 12, 0, 0, Math.PI * 2
                );
                ctx.fill();
                ctx.shadowBlur = 0;
                // Ботва (анимированная)
                ctx.strokeStyle = '#388e3c';
                ctx.lineWidth = 2;
                let sway = Math.sin(animationFrame/10 + i) * 2;
                ctx.beginPath();
                ctx.moveTo(carrot.x + CELL_SIZE/2, carrot.y + CELL_SIZE/2 - 2);
                ctx.lineTo(carrot.x + CELL_SIZE/2 + sway, carrot.y + CELL_SIZE/2 - 10);
                ctx.moveTo(carrot.x + CELL_SIZE/2, carrot.y + CELL_SIZE/2 - 2);
                ctx.lineTo(carrot.x + CELL_SIZE/2 - 3 + sway, carrot.y + CELL_SIZE/2 - 8);
                ctx.moveTo(carrot.x + CELL_SIZE/2, carrot.y + CELL_SIZE/2 - 2);
                ctx.lineTo(carrot.x + CELL_SIZE/2 + 3 + sway, carrot.y + CELL_SIZE/2 - 8);
                ctx.stroke();
                ctx.restore();
            });
        } else {
            // Используем кэширование для оптимизации (для заставки)
            const carrotCache = document.createElement('canvas');
            carrotCache.width = CELL_SIZE;
            carrotCache.height = CELL_SIZE;
            const carrotCtx = carrotCache.getContext('2d');
            
            // Рисуем одну морковку в кэш
            carrotCtx.save();
            carrotCtx.shadowColor = '#ff9800';
            carrotCtx.shadowBlur = 8;
            carrotCtx.fillStyle = '#ff9800';
            carrotCtx.beginPath();
            carrotCtx.ellipse(
                CELL_SIZE/2,
                CELL_SIZE/2 + 4,
                6, 12, 0, 0, Math.PI * 2
            );
            carrotCtx.fill();
            carrotCtx.shadowBlur = 0;
            
            // Ботва (статичная в кэше)
            carrotCtx.strokeStyle = '#388e3c';
            carrotCtx.lineWidth = 2;
            carrotCtx.beginPath();
            carrotCtx.moveTo(CELL_SIZE/2, CELL_SIZE/2 - 2);
            carrotCtx.lineTo(CELL_SIZE/2, CELL_SIZE/2 - 10);
            carrotCtx.moveTo(CELL_SIZE/2, CELL_SIZE/2 - 2);
            carrotCtx.lineTo(CELL_SIZE/2 - 3, CELL_SIZE/2 - 8);
            carrotCtx.moveTo(CELL_SIZE/2, CELL_SIZE/2 - 2);
            carrotCtx.lineTo(CELL_SIZE/2 + 3, CELL_SIZE/2 - 8);
            carrotCtx.stroke();
            carrotCtx.restore();
            
            // Отрисовываем все морковки, используя кэш
            carrots.forEach((carrot) => {
                if (isNaN(carrot.x) || isNaN(carrot.y)) {
                    console.error("Invalid carrot position", carrot);
                    return;
                }
                ctx.drawImage(carrotCache, carrot.x, carrot.y);
            });
        }
    } catch (error) {
        console.error("Error drawing carrots:", error);
    }
}

// --- Управление кроликом (плавное движение как у волков) ---
document.addEventListener('keydown', (e) => {
    if (!gameStarted || gamePaused) return;
    let handled = false;
    switch(e.key) {
        case 'ArrowUp': case 'w': case 'W': rabbit.nextDirection = 'up'; handled = true; break;
        case 'ArrowDown': case 's': case 'S': rabbit.nextDirection = 'down'; handled = true; break;
        case 'ArrowLeft': case 'a': case 'A': rabbit.nextDirection = 'left'; handled = true; break;
        case 'ArrowRight': case 'd': case 'D': rabbit.nextDirection = 'right'; handled = true; break;
    }
    if (handled) {
        e.preventDefault();
    }
});

function getOppositeDirection(dir) {
    switch(dir) {
        case 'up': return 'down';
        case 'down': return 'up';
        case 'left': return 'right';
        case 'right': return 'left';
    }
    return dir;
}

function centerInCell(obj) {
    try {
        if (!obj || typeof obj !== 'object') {
            console.error("Invalid object passed to centerInCell", obj);
            return;
        }
        
        // Безопасное получение координат
        const x = Number(obj.x) || 0;
        const y = Number(obj.y) || 0;
        
        const gridX = Math.floor((x + CELL_SIZE/2) / CELL_SIZE);
        const gridY = Math.floor((y + CELL_SIZE/2) / CELL_SIZE);
        
        // Проверяем, что координаты в пределах поля
        if (gridX >= 0 && gridX < GRID_WIDTH && gridY >= 0 && gridY < GRID_HEIGHT) {
            // Точное центрирование объекта в середине ячейки
            obj.x = gridX * CELL_SIZE;
            obj.y = gridY * CELL_SIZE;
            
            // Проверяем, что новая позиция не в стене
            if (maze[gridY][gridX] === 1) {
                console.error("Tried to center object in wall at", gridX, gridY);
                // Найдем ближайшую свободную ячейку
                for (let r = 1; r < 5; r++) {
                    for (let dy = -r; dy <= r; dy++) {
                        for (let dx = -r; dx <= r; dx++) {
                            const ny = gridY + dy;
                            const nx = gridX + dx;
                            if (nx >= 0 && nx < GRID_WIDTH && ny >= 0 && ny < GRID_HEIGHT && maze[ny][nx] === 0) {
                                obj.x = nx * CELL_SIZE;
                                obj.y = ny * CELL_SIZE;
                                console.log("Relocated object to safe cell", nx, ny);
                                return;
                            }
                        }
                    }
                }
            }
            
            console.log("Centered object at", obj.x, obj.y);
        } else {
            // Если координаты вышли за пределы поля, используем безопасное значение
            obj.x = CELL_SIZE;
            obj.y = CELL_SIZE;
            console.warn("Object outside grid bounds, using safe position", gridX, gridY);
        }
    } catch (error) {
        console.error("Error in centerInCell:", error);
    }
}

function moveRabbit() {
    // Сначала пробуем сменить направление, если возможно
    if (isCellCenter(rabbit.x, rabbit.y) && canMove(rabbit.x, rabbit.y, rabbit.nextDirection, rabbit.speed)) {
        const prevDirection = rabbit.direction;
        rabbit.direction = rabbit.nextDirection;
        // Центрируем только при смене направления
        if (prevDirection !== rabbit.direction) {
            centerInCell(rabbit);
        }
    }
    // Двигаем кролика, если возможно
    if (canMove(rabbit.x, rabbit.y, rabbit.direction, rabbit.speed)) {
        switch(rabbit.direction) {
            case 'up': rabbit.y -= rabbit.speed; break;
            case 'down': rabbit.y += rabbit.speed; break;
            case 'left': rabbit.x -= rabbit.speed; break;
            case 'right': rabbit.x += rabbit.speed; break;
        }
        // НЕ центрируем кролика после каждого движения для избежания топтания
    } else {
        // Если упёрся в стену — сразу разворачиваемся
        const opposite = getOppositeDirection(rabbit.direction);
        if (canMove(rabbit.x, rabbit.y, opposite, rabbit.speed)) {
            rabbit.direction = opposite;
            rabbit.nextDirection = opposite;
            // Центрируем только при упирании в стену
            centerInCell(rabbit);
        }
    }
}

// Game functions
function drawMaze() {
    // Проверка наличия контекста
    if (!ctx) {
        console.error("Canvas context is not available");
        return;
    }
    
    try {
        ctx.save();
        ctx.fillStyle = '#7ec850'; // светло-зелёный для сада
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        for (let y = 0; y < maze.length; y++) {
            for (let x = 0; x < maze[y].length; x++) {
                if (maze[y][x] === 1) {
                    ctx.fillStyle = '#3e5c2c'; // тёмно-зелёный для стен
                    ctx.strokeStyle = '#a5d6a7'; // светлая обводка
                    ctx.lineWidth = 2;
                    ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
                    ctx.strokeRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
                }
            }
        }
        ctx.restore();
    } catch (error) {
        console.error("Error drawing maze:", error);
    }
}

// Обновляем функцию gameLoop, добавляя проверку целостности объектов
function gameLoop(isFirstRun) {
    if (isFirstRun) {
        debugLog('GAMELOOP', 'First run of game loop');
        // Проверяем целостность объектов при первом запуске
        validateGameObjects();
    }
    
    if (!gameStarted || gamePaused) {
        debugLog('GAMELOOP', 'Game not active', { gameStarted, gamePaused });
        return;
    }
    
    animationFrame++;
    if (animationFrame % 30 === 0) {
        debugLog('GAMELOOP', `Frame ${animationFrame}`, { 
            rabbit: { x: rabbit.x, y: rabbit.y, dir: rabbit.direction },
            wolves: wolves.map(w => ({ x: w.x, y: w.y }))
        });
    }
    
    try {
        // Очистка холста
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Отрисовка элементов
        drawMaze();
        
        if (isFirstRun) {
            debugLog('RENDER', 'First render pass');
            debugLog('STATE', 'Canvas dimensions', { w: canvas.width, h: canvas.height });
        }
        
        // ВАЖНО: перемещение персонажей
        moveRabbit();
        moveWolves(); // Умное движение волков
        checkCollisions();
        
        // Принудительно вызываем каждую функцию отрисовки
        if (carrots && carrots.length > 0) {
            drawCarrots();
        } else {
            debugLog('WARNING', 'No carrots to draw');
        }
        
        if (wolves && wolves.length > 0) {
            drawWolves();
        } else {
            debugLog('WARNING', 'No wolves to draw');
        }
        
        drawRabbit();
        drawScore();
        
        if (carrots.length === 0) {
            // Победа
            debugLog('GAME', 'Victory!', { score });
            gameStarted = false;
            startScreen.innerHTML = `<h1>Победа!</h1><p>Счёт: ${score}</p><button id="startButton" class="btn btn-primary">Играть снова</button>`;
            startScreen.style.display = 'block';
            setTimeout(() => startScreen.style.opacity = 1, 10);
            setTimeout(() => {
                const newStartBtn = document.getElementById('startButton');
                if (newStartBtn) {
                    newStartBtn.onclick = () => {
                        debugLog('GAME', 'Restart after victory');
                        gameStarted = true;
                        gamePaused = false;
                        startScreen.style.opacity = 0;
                        setTimeout(() => startScreen.style.display = 'none', 400);
                        resetPositions();
                        resetCarrots();
                        score = 0;
                        lives = 3;
                        animationFrame = 0;
                        gameLoop(true);
                    };
                }
            }, 100);
            return;
        }
        
        // Продолжаем анимацию
        window.requestAnimationFrame(gameLoop);
    } catch (error) {
        debugLog('ERROR', 'Error in game loop', error.toString());
        debugLog('ERROR', 'Error stack', error.stack);
        
        // Восстанавливаем игру при ошибке
        setTimeout(() => {
            if (gameStarted && !gamePaused) {
                debugLog('RECOVERY', 'Attempting to recover game loop');
                // Проверяем целостность объектов при восстановлении после ошибки
                validateGameObjects();
                requestAnimationFrame(gameLoop);
            }
        }, 1000);
    }
}

function drawRabbit() {
    try {
        // Проверка позиции
        if (isNaN(rabbit.x) || isNaN(rabbit.y)) {
            debugLog('ERROR', 'Invalid rabbit position', rabbit);
            centerInCell(rabbit); // Исправляем позицию
        }
        
        debugLog('RENDER', 'Drawing rabbit', { x: rabbit.x, y: rabbit.y });
        
        // Тело
        ctx.save();
        ctx.shadowColor = '#fff';
        ctx.shadowBlur = 8;
        ctx.fillStyle = '#fff';
        ctx.beginPath();
        ctx.arc(
            rabbit.x + CELL_SIZE/2,
            rabbit.y + CELL_SIZE/2,
            rabbit.size/2,
            0,
            Math.PI * 2
        );
        ctx.fill();
        
        // Проверим, был ли нарисован кролик
        const imgData = ctx.getImageData(rabbit.x + CELL_SIZE/2, rabbit.y + CELL_SIZE/2, 1, 1);
        const pixelData = imgData.data;
        debugLog('RENDER', 'Rabbit pixel data', Array.from(pixelData));
        
        ctx.shadowBlur = 0;
        // Ушки (анимированные)
        ctx.save();
        ctx.fillStyle = '#fff';
        let earOffset = Math.sin(animationFrame/8) * 2;
        ctx.fillRect(rabbit.x + 8, rabbit.y - 2 - earOffset, 4, 14 + earOffset);
        ctx.fillRect(rabbit.x + 20, rabbit.y - 2 - earOffset, 4, 14 + earOffset);
        ctx.restore();
        // Глазки
        ctx.fillStyle = '#222';
        ctx.beginPath();
        ctx.arc(rabbit.x + 13, rabbit.y + 18, 2, 0, Math.PI * 2);
        ctx.arc(rabbit.x + 19, rabbit.y + 18, 2, 0, Math.PI * 2);
        ctx.fill();
        // Нос
        ctx.fillStyle = '#f9a825';
        ctx.beginPath();
        ctx.arc(rabbit.x + CELL_SIZE/2, rabbit.y + CELL_SIZE/2 + 6, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
    } catch (error) {
        debugLog('ERROR', 'Error drawing rabbit', error.toString());
    }
}

function drawWolves() {
    try {
        console.log("Drawing wolves", wolves.length);
        wolves.forEach((wolf, index) => {
            // Проверка позиции
            if (isNaN(wolf.x) || isNaN(wolf.y)) {
                console.error("Invalid wolf position", wolf);
                centerInCell(wolf); // Исправляем позицию
                return; // Пропускаем этого волка
            }
            
            ctx.save();
            ctx.shadowColor = '#888';
            ctx.shadowBlur = 8;
            // Тело
            ctx.fillStyle = '#888';
            ctx.beginPath();
            ctx.arc(wolf.x + CELL_SIZE/2, wolf.y + CELL_SIZE/2, (CELL_SIZE-4)/2, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
            // Ушки
            ctx.fillStyle = '#666';
            ctx.beginPath();
            ctx.moveTo(wolf.x + 8, wolf.y + 8);
            ctx.lineTo(wolf.x + 14, wolf.y - 4);
            ctx.lineTo(wolf.x + 20, wolf.y + 8);
            ctx.closePath();
            ctx.fill();
            ctx.beginPath();
            ctx.moveTo(wolf.x + 24, wolf.y + 8);
            ctx.lineTo(wolf.x + 18, wolf.y - 4);
            ctx.lineTo(wolf.x + 12, wolf.y + 8);
            ctx.closePath();
            ctx.fill();
            // Глазки
            ctx.fillStyle = '#222';
            ctx.beginPath();
            ctx.arc(wolf.x + 13, wolf.y + 18, 2, 0, Math.PI * 2);
            ctx.arc(wolf.x + 19, wolf.y + 18, 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        });
    } catch (error) {
        console.error("Error drawing wolves:", error);
    }
}

// Добавить умную функцию moveWolves
function moveWolves() {
    // Отладочное сообщение о вызове функции
    console.log("MOVING WOLVES: ", wolves.length);
    
    wolves.forEach((wolf, index) => {
        try {
            // Если волк не имеет направления, задаем случайное
            if (!wolf.direction || wolf.direction === '') {
                wolf.direction = ['up', 'down', 'left', 'right'][Math.floor(Math.random() * 4)];
                console.log(`Wolf ${index} got random direction: ${wolf.direction}`);
            }
            
            // Координаты в сетке для волка и кролика
            const wolfGridX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
            const wolfGridY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
            const rabbitGridX = Math.floor((rabbit.x + CELL_SIZE/2) / CELL_SIZE);
            const rabbitGridY = Math.floor((rabbit.y + CELL_SIZE/2) / CELL_SIZE);
            
            // Принимаем решение о направлении только в центре ячейки
            if (isCellCenter(wolf.x, wolf.y)) {
                // Не центрируем каждый раз, чтобы избежать "топтания" на месте
                
                // Проверяем видимость кролика (без стен между ними)
                const canSeeRabbit = checkLineOfSight(wolfGridX, wolfGridY, rabbitGridX, rabbitGridY);
                let nextDirection = wolf.direction;
                
                if (canSeeRabbit) {
                    // Если кролик виден напрямую, преследуем его
                    if (Math.abs(wolfGridX - rabbitGridX) > Math.abs(wolfGridY - rabbitGridY)) {
                        // Приоритет горизонтального движения
                        if (wolfGridX < rabbitGridX) nextDirection = 'right';
                        else if (wolfGridX > rabbitGridX) nextDirection = 'left';
                    } else {
                        // Приоритет вертикального движения
                        if (wolfGridY < rabbitGridY) nextDirection = 'down';
                        else if (wolfGridY > rabbitGridY) nextDirection = 'up';
                    }
                } else {
                    // Если кролик не виден, используем более случайное движение
                    if (index % 2 === 0) {
                        // Для четных волков: пытаемся преследовать, но с большей случайностью
                        if (Math.random() < 0.6) {
                            // 60% времени используем общее направление к кролику
                            if (Math.abs(wolfGridX - rabbitGridX) > Math.abs(wolfGridY - rabbitGridY)) {
                                if (wolfGridX < rabbitGridX) nextDirection = 'right';
                                else if (wolfGridX > rabbitGridX) nextDirection = 'left';
                            } else {
                                if (wolfGridY < rabbitGridY) nextDirection = 'down';
                                else if (wolfGridY > rabbitGridY) nextDirection = 'up';
                            }
                        } else {
                            // 40% времени выбираем случайное направление
                            const availableDirs = getAvailableDirections(wolf);
                            if (availableDirs.length > 0) {
                                nextDirection = availableDirs[Math.floor(Math.random() * availableDirs.length)];
                            }
                        }
                    } else {
                        // Для нечетных волков: более случайное движение
                        if (Math.random() < 0.3) {
                            // 30% времени пытаемся двигаться к кролику
                            if (Math.random() < 0.5) {
                                if (wolfGridX < rabbitGridX) nextDirection = 'right';
                                else if (wolfGridX > rabbitGridX) nextDirection = 'left';
                            } else {
                                if (wolfGridY < rabbitGridY) nextDirection = 'down';
                                else if (wolfGridY > rabbitGridY) nextDirection = 'up';
                            }
                        } else {
                            // 70% времени выбираем случайное направление
                            const availableDirs = getAvailableDirections(wolf);
                            if (availableDirs.length > 0) {
                                nextDirection = availableDirs[Math.floor(Math.random() * availableDirs.length)];
                            }
                        }
                    }
                }
                
                // Проверяем, можем ли двигаться в выбранном направлении
                if (!canMove(wolf.x, wolf.y, nextDirection, wolf.speed)) {
                    // Если не можем, выбираем из доступных направлений
                    const availableDirs = getAvailableDirections(wolf);
                    if (availableDirs.length > 0) {
                        nextDirection = availableDirs[Math.floor(Math.random() * availableDirs.length)];
                    }
                }
                
                // Устанавливаем новое направление
                if (wolf.direction !== nextDirection) {
                    console.log(`Wolf ${index} changed direction: ${wolf.direction} -> ${nextDirection}`);
                    wolf.direction = nextDirection;
                    
                    // Центрируем только при смене направления
                    centerInCell(wolf);
                }
            }
            
            // Двигаем волка в текущем направлении
            // Проверяем, можем ли двигаться вперед
            if (canMove(wolf.x, wolf.y, wolf.direction, wolf.speed)) {
                switch(wolf.direction) {
                    case 'up': wolf.y -= wolf.speed; break;
                    case 'down': wolf.y += wolf.speed; break;
                    case 'left': wolf.x -= wolf.speed; break;
                    case 'right': wolf.x += wolf.speed; break;
                    default: 
                        wolf.direction = 'right';
                        if (canMove(wolf.x, wolf.y, 'right', wolf.speed)) {
                            wolf.x += wolf.speed;
                        }
                }
            } else {
                // Если не можем двигаться, пытаемся сменить направление
                const availableDirs = getAvailableDirections(wolf);
                if (availableDirs.length > 0) {
                    wolf.direction = availableDirs[Math.floor(Math.random() * availableDirs.length)];
                    console.log(`Wolf ${index} blocked, new direction: ${wolf.direction}`);
                }
            }
            
        } catch (error) {
            console.error(`Error moving wolf ${index}:`, error);
            centerInCell(wolf);
        }
    });
    
    // Выводим периодически информацию о позициях волков
    if (animationFrame % 30 === 0) {
        console.log("Wolf positions:", wolves.map(wolf => ({
            x: Math.floor(wolf.x/CELL_SIZE),
            y: Math.floor(wolf.y/CELL_SIZE),
            dir: wolf.direction
        })));
    }
}

// Функция для проверки прямой видимости между клетками (без стен)
function checkLineOfSight(x1, y1, x2, y2) {
    // Если координаты совпадают, то видимость есть
    if (x1 === x2 && y1 === y2) return true;
    
    // Пока работаем только по прямым линиям (горизонталь/вертикаль)
    // т.к. в Pac-Man персонажи всегда двигаются только по прямым
    
    // Проверка по горизонтали
    if (y1 === y2) {
        const start = Math.min(x1, x2);
        const end = Math.max(x1, x2);
        for (let x = start + 1; x < end; x++) {
            if (maze[y1][x] === 1) return false; // Есть стена между x1 и x2
        }
        return true;
    }
    
    // Проверка по вертикали
    if (x1 === x2) {
        const start = Math.min(y1, y2);
        const end = Math.max(y1, y2);
        for (let y = start + 1; y < end; y++) {
            if (maze[y][x1] === 1) return false; // Есть стена между y1 и y2
        }
        return true;
    }
    
    // По диагонали прямой видимости нет в игре типа Pac-Man
    return false;
}

// Функция для получения доступных направлений движения для волка
function getAvailableDirections(wolf) {
    // Проверяем все 4 направления
    const directions = ['up', 'down', 'left', 'right'];
    return directions.filter(dir => canMove(wolf.x, wolf.y, dir, wolf.speed));
}

function isCellCenter(x, y) {
    // Проверка: находится ли объект в центре клетки
    return (
        Math.abs((x + CELL_SIZE / 2) % CELL_SIZE - CELL_SIZE / 2) < 2 &&
        Math.abs((y + CELL_SIZE / 2) % CELL_SIZE - CELL_SIZE / 2) < 2
    );
}

function canMove(x, y, direction, speed) {
    // Начальная проверка валидности координат
    if (x === undefined || y === undefined || !direction) {
        console.error("Invalid parameters in canMove:", {x, y, direction, speed});
        return false;
    }
    
    let newX = x;
    let newY = y;
    switch(direction) {
        case 'up': newY -= speed; break;
        case 'down': newY += speed; break;
        case 'left': newX -= speed; break;
        case 'right': newX += speed; break;
        default: 
            console.warn("Unknown direction:", direction);
            return false;
    }
    
    // Проверка границ после вычисления новых координат
    const gridX = Math.floor((newX + CELL_SIZE/2) / CELL_SIZE);
    const gridY = Math.floor((newY + CELL_SIZE/2) / CELL_SIZE);
    
    // Двойная проверка на выход за границы массива maze
    if (gridX < 0 || gridX >= GRID_WIDTH || gridY < 0 || gridY >= GRID_HEIGHT) {
        return false;
    }
    
    // Проверяем, что maze и maze[gridY] существуют
    if (!maze || !maze[gridY]) {
        console.error("Invalid maze or row in canMove:", {gridX, gridY});
        return false;
    }
    
    return maze[gridY][gridX] !== 1;
}

function alignToFreeCell(obj) {
    // Находим ближайший центр свободной клетки
    let minDist = Infinity;
    let best = {x: obj.x, y: obj.y};
    for (let j = 0; j < GRID_HEIGHT; j++) {
        for (let i = 0; i < GRID_WIDTH; i++) {
            if (maze[j][i] === 0) {
                let cx = i * CELL_SIZE;
                let cy = j * CELL_SIZE;
                let dist = Math.hypot(obj.x - cx, obj.y - cy);
                if (dist < minDist) {
                    minDist = dist;
                    best = {x: cx, y: cy};
                }
            }
        }
    }
    obj.x = best.x;
    obj.y = best.y;
}

// Добавляем функции для улучшенного AI волков
function canSeeRabbit(wolf) {
    try {
        // Проверка на валидность объектов
        if (!wolf || !rabbit) {
            console.error("Invalid objects in canSeeRabbit");
            return false;
        }
        
        const wolfGridX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
        const wolfGridY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
        const rabbitGridX = Math.floor((rabbit.x + CELL_SIZE/2) / CELL_SIZE);
        const rabbitGridY = Math.floor((rabbit.y + CELL_SIZE/2) / CELL_SIZE);
        
        // Проверка на валидность координат
        if (wolfGridX < 0 || wolfGridX >= GRID_WIDTH || wolfGridY < 0 || wolfGridY >= GRID_HEIGHT ||
            rabbitGridX < 0 || rabbitGridX >= GRID_WIDTH || rabbitGridY < 0 || rabbitGridY >= GRID_HEIGHT) {
            return false;
        }
        
        // Проверяем, находится ли кролик в той же строке или столбце
        if (wolfGridX === rabbitGridX || wolfGridY === rabbitGridY) {
            // Проверяем, нет ли стен между волком и кроликом
            if (wolfGridX === rabbitGridX) {
                const startY = Math.min(wolfGridY, rabbitGridY);
                const endY = Math.max(wolfGridY, rabbitGridY);
                for (let y = startY + 1; y < endY; y++) {
                    if (maze[y][wolfGridX] === 1) return false;
                }
                return true;
            } else {
                const startX = Math.min(wolfGridX, rabbitGridX);
                const endX = Math.max(wolfGridX, rabbitGridX);
                for (let x = startX + 1; x < endX; x++) {
                    if (maze[wolfGridY][x] === 1) return false;
                }
                return true;
            }
        }
        return false;
    } catch (error) {
        console.error("Error in canSeeRabbit:", error);
        return false;
    }
}

function findPathToRabbit(wolf) {
    const wolfGridX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
    const wolfGridY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
    const rabbitGridX = Math.floor((rabbit.x + CELL_SIZE/2) / CELL_SIZE);
    const rabbitGridY = Math.floor((rabbit.y + CELL_SIZE/2) / CELL_SIZE);
    
    // Простой алгоритм поиска пути
    const directions = ['up', 'down', 'left', 'right'];
    let bestDir = wolf.direction;
    let minDist = Infinity;
    
    for (const dir of directions) {
        if (canMove(wolf.x, wolf.y, dir, wolf.speed)) {
            let newX = wolfGridX;
            let newY = wolfGridY;
            switch(dir) {
                case 'up': newY--; break;
                case 'down': newY++; break;
                case 'left': newX--; break;
                case 'right': newX++; break;
            }
            const dist = Math.hypot(newX - rabbitGridX, newY - rabbitGridY);
            if (dist < minDist) {
                minDist = dist;
                bestDir = dir;
            }
        }
    }
    return bestDir;
}

function generatePatrolPath(wolf) {
    try {
        const path = [];
        const visited = new Set();
        const startX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
        const startY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
        
        // Проверяем валидность начальной позиции
        if (startX < 0 || startX >= GRID_WIDTH || startY < 0 || startY >= GRID_HEIGHT || maze[startY][startX] === 1) {
            // Если начальная позиция недействительна, вернем простой путь
            console.error("Invalid wolf starting position for patrol path", startX, startY);
            return [{x: 1, y: 1}];
        }
        
        function dfs(x, y, depth = 0) {
            if (depth > 15 || path.length > 20) return; // Ограничиваем глубину и длину пути
            if (x < 0 || x >= GRID_WIDTH || y < 0 || y >= GRID_HEIGHT || maze[y][x] === 1) return;
            const key = `${x},${y}`;
            if (visited.has(key)) return;
            
            visited.add(key);
            path.push({x, y});
            
            const directions = [
                {dx: 0, dy: -1}, // up
                {dx: 0, dy: 1},  // down
                {dx: -1, dy: 0}, // left
                {dx: 1, dy: 0}   // right
            ];
            
            // Перемешиваем направления для разнообразия
            directions.sort(() => Math.random() - 0.5);
            
            for (const {dx, dy} of directions) {
                dfs(x + dx, y + dy, depth + 1);
            }
        }
        
        dfs(startX, startY);
        
        // Если маршрут пустой, добавляем хотя бы одну точку
        if (path.length === 0) {
            path.push({x: startX, y: startY});
        }
        
        return path;
    } catch (error) {
        console.error("Error generating patrol path:", error);
        return [{x: 1, y: 1}]; // Возвращаем безопасный маршрут в случае ошибки
    }
}

function checkCollisions() {
    // Check carrot collection
    carrots = carrots.filter(carrot => {
        const distance = Math.hypot(rabbit.x + CELL_SIZE/2 - (carrot.x + CELL_SIZE/2), rabbit.y + CELL_SIZE/2 - (carrot.y + CELL_SIZE/2));
        if (distance < CELL_SIZE/2) {
            score += 10;
            return false;
        }
        return true;
    });
    // Check wolf collisions
    wolves.forEach(wolf => {
        const distance = Math.hypot(rabbit.x + CELL_SIZE/2 - (wolf.x + CELL_SIZE/2), rabbit.y + CELL_SIZE/2 - (wolf.y + CELL_SIZE/2));
        if (distance < CELL_SIZE/2) {
            lives--;
            if (lives <= 0) {
                gameOver();
            } else {
                resetPositions();
            }
        }
    });
}

function resetPositions() {
    console.log("Resetting positions");
    
    // Сбрасываем позицию кролика - точно в центре ячейки
    rabbit.x = 7 * CELL_SIZE;
    rabbit.y = 11 * CELL_SIZE;
    centerInCell(rabbit);
    rabbit.direction = '';
    rabbit.nextDirection = '';
    
    // Определяем безопасные начальные клетки для волков
    const safeWolfPositions = [
        { x: 6, y: 5 },
        { x: 8, y: 5 },
        { x: 6, y: 6 },
        { x: 8, y: 6 }
    ];
    
    // Проверяем, что позиции находятся на свободных клетках
    safeWolfPositions.forEach(pos => {
        if (maze[pos.y][pos.x] !== 0) {
            console.error(`Invalid wolf position at ${pos.x},${pos.y}, adjusting...`);
            // Находим ближайшую свободную клетку
            let found = false;
            for (let r = 1; r < 5 && !found; r++) {
                for (let dy = -r; dy <= r && !found; dy++) {
                    for (let dx = -r; dx <= r && !found; dx++) {
                        const ny = pos.y + dy;
                        const nx = pos.x + dx;
                        if (nx >= 0 && nx < GRID_WIDTH && ny >= 0 && ny < GRID_HEIGHT && maze[ny][nx] === 0) {
                            pos.x = nx;
                            pos.y = ny;
                            found = true;
                            console.log(`Wolf relocated to safe position at ${nx},${ny}`);
                        }
                    }
                }
            }
            
            if (!found) {
                // Если не нашли безопасную позицию, используем гарантированно свободную клетку
                pos.x = 1;
                pos.y = 1;
                console.warn("Using failsafe wolf position at 1,1");
            }
        }
    });
    
    // Полностью пересоздаем массив волков с безопасными координатами
    wolves.length = 0;
    
    // Начальные направления для более предсказуемого движения
    const initialDirections = ['right', 'left', 'up', 'down'];
    
    // Создаем новых волков с простыми базовыми настройками
    safeWolfPositions.forEach((pos, index) => {
        const wolf = { 
            x: pos.x * CELL_SIZE, 
            y: pos.y * CELL_SIZE, 
            direction: initialDirections[index % 4], 
            speed: 1.5,
            state: 'normal'
        };
        
        // Центрируем волка в клетке
        centerInCell(wolf);
        
        // Дополнительная проверка позиции
        const gridX = Math.floor((wolf.x + CELL_SIZE/2) / CELL_SIZE);
        const gridY = Math.floor((wolf.y + CELL_SIZE/2) / CELL_SIZE);
        if (maze[gridY][gridX] !== 0) {
            console.error(`Wolf ${index} still in wall after centering, forcing to 1,1`);
            wolf.x = CELL_SIZE;
            wolf.y = CELL_SIZE;
        }
        
        // Добавляем волка в массив
        wolves.push(wolf);
    });
    
    console.log("Positions reset", { rabbit, wolves });
}

function drawScore() {
    ctx.save();
    ctx.fillStyle = 'white';
    ctx.font = 'bold 20px Arial';
    ctx.shadowColor = '#222';
    ctx.shadowBlur = 4;
    ctx.fillText(`Счёт: ${score}`, 10, 30);
    ctx.fillText(`Жизни: ${lives}`, canvas.width - 120, 30);
    ctx.restore();
}

function gameOver() {
    gameStarted = false;
    if (!startScreen) return;
    
    startScreen.innerHTML = `
        <h1>Игра окончена</h1>
        <p>Счёт: ${score}</p>
        <button id="startButton" class="btn btn-primary">Играть снова</button>
    `;
    startScreen.style.display = 'block';
    setTimeout(() => startScreen.style.opacity = 1, 10);
    // Повторно навешиваем обработчик на новую кнопку
    setTimeout(() => {
        const newStartBtn = document.getElementById('startButton');
        if (newStartBtn) {
            newStartBtn.onclick = () => {
                gameStarted = true;
                gamePaused = false;
                startScreen.style.opacity = 0;
                setTimeout(() => startScreen.style.display = 'none', 400);
                resetPositions();
                resetCarrots();
                score = 0;
                lives = 3;
                animationFrame = 0;
                gameLoop();
            };
        }
    }, 100);
}

// Show start screen initially
if (startScreen) {
    startScreen.style.display = 'block';
    startScreen.style.opacity = 1;
    
    // Отрисовываем элементы игры сразу
    setTimeout(initGameElements, 100);
    
    // Инициализируем стартовую кнопку
    setupStartButton();
}
}); 