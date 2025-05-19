const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const startScreen = document.getElementById('startScreen');
const startButton = document.getElementById('startButton');

// Set canvas size
canvas.width = 448;
canvas.height = 496;

// Game constants
const CELL_SIZE = 16;
const GRID_WIDTH = 28;
const GRID_HEIGHT = 31;

// Game state
let gameStarted = false;
let score = 0;
let lives = 3;

// Rabbit properties
const rabbit = {
    x: 14 * CELL_SIZE,
    y: 23 * CELL_SIZE,
    direction: 'right',
    speed: 2,
    size: CELL_SIZE - 2
};

// Wolves (enemies) properties
const wolves = [
    { x: 13 * CELL_SIZE, y: 11 * CELL_SIZE, direction: 'right', speed: 1.5 },
    { x: 14 * CELL_SIZE, y: 11 * CELL_SIZE, direction: 'left', speed: 1.5 },
    { x: 13 * CELL_SIZE, y: 12 * CELL_SIZE, direction: 'up', speed: 1.5 },
    { x: 14 * CELL_SIZE, y: 12 * CELL_SIZE, direction: 'down', speed: 1.5 }
];

// Carrots (food) properties
let carrots = [];
for (let i = 0; i < GRID_WIDTH; i++) {
    for (let j = 0; j < GRID_HEIGHT; j++) {
        if (i > 0 && i < GRID_WIDTH - 1 && j > 0 && j < GRID_HEIGHT - 1) {
            carrots.push({ x: i * CELL_SIZE, y: j * CELL_SIZE });
        }
    }
}

// Maze layout (1 represents walls)
const maze = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,0,1,1,1,1,1,0,1,1,0,1,1,1,1,1,0,1,1,1,1,0,1],
    [1,0,1,1,1,1,0,1,1,1,1,1,0,1,1,0,1,1,1,1,1,0,1,1,1,1,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,0,1,1,0,1,1,1,1,1,1,1,1,0,1,1,0,1,1,1,1,0,1],
    [1,0,0,0,0,0,0,1,1,0,0,0,0,1,1,0,0,0,0,1,1,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,0,1,1,1,1,1,0,1,1,0,1,1,1,1,1,0,1,1,1,1,1,1],
    [1,1,1,1,1,1,0,1,1,0,0,0,0,0,0,0,0,0,0,1,1,0,1,1,1,1,1,1],
    [1,1,1,1,1,1,0,1,1,0,1,1,1,0,0,1,1,1,0,1,1,0,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0],
    [1,1,1,1,1,1,0,1,1,0,1,1,1,1,1,1,1,1,0,1,1,0,1,1,1,1,1,1],
    [1,1,1,1,1,1,0,1,1,0,0,0,0,0,0,0,0,0,0,1,1,0,1,1,1,1,1,1],
    [1,1,1,1,1,1,0,1,1,0,1,1,1,1,1,1,1,1,0,1,1,0,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,0,1,1,1,1,1,0,1,1,0,1,1,1,1,1,0,1,1,1,1,0,1],
    [1,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,0,0,1],
    [1,1,1,0,1,1,0,1,1,0,1,1,1,1,1,1,1,1,0,1,1,0,1,1,0,1,1,1],
    [1,0,0,0,0,0,0,1,1,0,0,0,0,1,1,0,0,0,0,1,1,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,1,1,1,1,0,1,1,0,1,1,1,1,1,1,1,1,1,1,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
];

// Event listeners
startButton.addEventListener('click', () => {
    gameStarted = true;
    startScreen.style.display = 'none';
    gameLoop();
});

document.addEventListener('keydown', (e) => {
    if (!gameStarted) return;
    
    switch(e.key) {
        case 'ArrowUp':
            rabbit.direction = 'up';
            break;
        case 'ArrowDown':
            rabbit.direction = 'down';
            break;
        case 'ArrowLeft':
            rabbit.direction = 'left';
            break;
        case 'ArrowRight':
            rabbit.direction = 'right';
            break;
    }
});

// Game functions
function drawMaze() {
    for (let y = 0; y < maze.length; y++) {
        for (let x = 0; x < maze[y].length; x++) {
            if (maze[y][x] === 1) {
                ctx.fillStyle = '#34495e';
                ctx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
            }
        }
    }
}

function drawRabbit() {
    ctx.fillStyle = '#f1c40f';
    ctx.beginPath();
    ctx.arc(
        rabbit.x + CELL_SIZE/2,
        rabbit.y + CELL_SIZE/2,
        rabbit.size/2,
        0,
        Math.PI * 2
    );
    ctx.fill();
    
    // Draw ears
    ctx.fillStyle = '#f1c40f';
    ctx.fillRect(rabbit.x + 4, rabbit.y - 4, 4, 8);
    ctx.fillRect(rabbit.x + 12, rabbit.y - 4, 4, 8);
}

function drawWolves() {
    wolves.forEach(wolf => {
        ctx.fillStyle = '#e74c3c';
        ctx.fillRect(wolf.x, wolf.y, CELL_SIZE - 2, CELL_SIZE - 2);
    });
}

function drawCarrots() {
    carrots.forEach(carrot => {
        ctx.fillStyle = '#e67e22';
        ctx.beginPath();
        ctx.moveTo(carrot.x + CELL_SIZE/2, carrot.y);
        ctx.lineTo(carrot.x + CELL_SIZE, carrot.y + CELL_SIZE);
        ctx.lineTo(carrot.x, carrot.y + CELL_SIZE);
        ctx.closePath();
        ctx.fill();
    });
}

function moveRabbit() {
    let newX = rabbit.x;
    let newY = rabbit.y;
    
    switch(rabbit.direction) {
        case 'up':
            newY -= rabbit.speed;
            break;
        case 'down':
            newY += rabbit.speed;
            break;
        case 'left':
            newX -= rabbit.speed;
            break;
        case 'right':
            newX += rabbit.speed;
            break;
    }
    
    // Check collision with walls
    const gridX = Math.floor(newX / CELL_SIZE);
    const gridY = Math.floor(newY / CELL_SIZE);
    
    if (gridX >= 0 && gridX < GRID_WIDTH && gridY >= 0 && gridY < GRID_HEIGHT) {
        if (maze[gridY][gridX] !== 1) {
            rabbit.x = newX;
            rabbit.y = newY;
        }
    }
}

function moveWolves() {
    wolves.forEach(wolf => {
        let newX = wolf.x;
        let newY = wolf.y;
        
        // Simple AI: Move towards rabbit
        if (Math.random() < 0.1) {
            if (Math.abs(wolf.x - rabbit.x) > Math.abs(wolf.y - rabbit.y)) {
                wolf.direction = wolf.x < rabbit.x ? 'right' : 'left';
            } else {
                wolf.direction = wolf.y < rabbit.y ? 'down' : 'up';
            }
        }
        
        switch(wolf.direction) {
            case 'up':
                newY -= wolf.speed;
                break;
            case 'down':
                newY += wolf.speed;
                break;
            case 'left':
                newX -= wolf.speed;
                break;
            case 'right':
                newX += wolf.speed;
                break;
        }
        
        // Check collision with walls
        const gridX = Math.floor(newX / CELL_SIZE);
        const gridY = Math.floor(newY / CELL_SIZE);
        
        if (gridX >= 0 && gridX < GRID_WIDTH && gridY >= 0 && gridY < GRID_HEIGHT) {
            if (maze[gridY][gridX] !== 1) {
                wolf.x = newX;
                wolf.y = newY;
            } else {
                // Change direction if hitting a wall
                const directions = ['up', 'down', 'left', 'right'];
                wolf.direction = directions[Math.floor(Math.random() * 4)];
            }
        }
    });
}

function checkCollisions() {
    // Check carrot collection
    carrots = carrots.filter(carrot => {
        const distance = Math.sqrt(
            Math.pow(rabbit.x - carrot.x, 2) + 
            Math.pow(rabbit.y - carrot.y, 2)
        );
        if (distance < CELL_SIZE) {
            score += 10;
            return false;
        }
        return true;
    });
    
    // Check wolf collisions
    wolves.forEach(wolf => {
        const distance = Math.sqrt(
            Math.pow(rabbit.x - wolf.x, 2) + 
            Math.pow(rabbit.y - wolf.y, 2)
        );
        if (distance < CELL_SIZE) {
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
    rabbit.x = 14 * CELL_SIZE;
    rabbit.y = 23 * CELL_SIZE;
    wolves[0].x = 13 * CELL_SIZE;
    wolves[0].y = 11 * CELL_SIZE;
    wolves[1].x = 14 * CELL_SIZE;
    wolves[1].y = 11 * CELL_SIZE;
    wolves[2].x = 13 * CELL_SIZE;
    wolves[2].y = 12 * CELL_SIZE;
    wolves[3].x = 14 * CELL_SIZE;
    wolves[3].y = 12 * CELL_SIZE;
}

function gameOver() {
    gameStarted = false;
    startScreen.style.display = 'block';
    startScreen.innerHTML = `
        <h1>Game Over</h1>
        <p>Score: ${score}</p>
        <button id="startButton">Play Again</button>
    `;
    score = 0;
    lives = 3;
    resetPositions();
}

function drawScore() {
    ctx.fillStyle = 'white';
    ctx.font = '20px Arial';
    ctx.fillText(`Score: ${score}`, 10, 30);
    ctx.fillText(`Lives: ${lives}`, canvas.width - 100, 30);
}

function gameLoop() {
    if (!gameStarted) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    drawMaze();
    moveRabbit();
    moveWolves();
    checkCollisions();
    
    drawCarrots();
    drawWolves();
    drawRabbit();
    drawScore();
    
    requestAnimationFrame(gameLoop);
}

// Show start screen initially
startScreen.style.display = 'block'; 