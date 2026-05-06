#!/usr/bin/env python3
"""贪吃蛇小游戏"""

import pygame
import random
import sys

# 初始化 pygame
pygame.init()

# 游戏常量
WINDOW_WIDTH = 640
WINDOW_HEIGHT = 480
CELL_SIZE = 20
FPS = 10

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 200, 0)
RED = (255, 0, 0)


class Snake:
    """蛇类"""

    def __init__(self):
        self.reset()

    def reset(self):
        # 初始位置在窗口中间
        start_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2
        self.body = [(start_x, start_y), (start_x - CELL_SIZE, start_y),
                     (start_x - 2 * CELL_SIZE, start_y)]
        self.direction = (CELL_SIZE, 0)  # 向右移动
        self.grow = False

    def get_head(self):
        return self.body[0]

    def move(self):
        head_x, head_y = self.get_head()
        dir_x, dir_y = self.direction
        new_head = (head_x + dir_x, head_y + dir_y)
        self.body.insert(0, new_head)
        if not self.grow:
            self.body.pop()
        else:
            self.grow = False

    def change_direction(self, new_direction):
        # 防止反向移动
        if (new_direction[0] != -self.direction[0] or
                new_direction[1] != -self.direction[1]):
            self.direction = new_direction

    def check_collision(self):
        head_x, head_y = self.get_head()
        # 穿墙：自动从另一侧出现
        if head_x < 0:
            head_x = WINDOW_WIDTH - CELL_SIZE
        elif head_x >= WINDOW_WIDTH:
            head_x = 0
        if head_y < 0:
            head_y = WINDOW_HEIGHT - CELL_SIZE
        elif head_y >= WINDOW_HEIGHT:
            head_y = 0
        # 更新头部位置
        self.body[0] = (head_x, head_y)
        # 撞自身检测
        head = (head_x, head_y)
        if head in self.body[1:]:
            return True
        return False

    def eat(self):
        self.grow = True


class Food:
    """食物类"""

    def __init__(self):
        self.position = (0, 0)
        self.spawn()

    def spawn(self, snake_body=None):
        while True:
            x = random.randint(0, (WINDOW_WIDTH - CELL_SIZE) // CELL_SIZE) * CELL_SIZE
            y = random.randint(0, (WINDOW_HEIGHT - CELL_SIZE) // CELL_SIZE) * CELL_SIZE
            self.position = (x, y)
            # 确保食物不会生成在蛇身上
            if snake_body is None or self.position not in snake_body:
                break

    def get_position(self):
        return self.position


class Game:
    """游戏主类"""

    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption('贪吃蛇')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.reset_game()

    def reset_game(self):
        self.snake = Snake()
        self.food = Food()
        self.score = 0
        self.game_over = False
        self.food.spawn(self.snake.body)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if self.game_over:
                    if event.key == pygame.K_SPACE:
                        self.reset_game()
                    elif event.key == pygame.K_ESCAPE:
                        return False
                else:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.snake.change_direction((0, -CELL_SIZE))
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.snake.change_direction((0, CELL_SIZE))
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self.snake.change_direction((-CELL_SIZE, 0))
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.snake.change_direction((CELL_SIZE, 0))
                    elif event.key == pygame.K_ESCAPE:
                        return False
        return True

    def update(self):
        if self.game_over:
            return
        self.snake.move()
        # 检测是否吃到食物
        if self.snake.get_head() == self.food.get_position():
            self.snake.eat()
            self.score += 10
            self.food.spawn(self.snake.body)
        # 检测碰撞
        if self.snake.check_collision():
            self.game_over = True

    def draw(self):
        self.screen.fill(BLACK)
        
        # 绘制蛇
        for i, segment in enumerate(self.snake.body):
            color = DARK_GREEN if i == 0 else GREEN
            rect = pygame.Rect(segment[0], segment[1], CELL_SIZE, CELL_SIZE)
            pygame.draw.rect(self.screen, color, rect)
            # 给蛇身加个边框
            pygame.draw.rect(self.screen, BLACK, rect, 1)
        
        # 绘制食物
        food_rect = pygame.Rect(self.food.get_position()[0], 
                               self.food.get_position()[1], 
                               CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(self.screen, RED, food_rect)
        pygame.draw.rect(self.screen, BLACK, food_rect, 1)
        
        # 绘制分数
        score_text = self.font.render(f'Score: {self.score}', True, WHITE)
        self.screen.blit(score_text, (10, 10))
        
        # 游戏结束画面
        if self.game_over:
            overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            overlay.set_alpha(128)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))
            
            game_over_text = self.font.render('Game Over!', True, WHITE)
            score_text = self.font.render(f'Final Score: {self.score}', True, WHITE)
            restart_text = self.font.render('Press SPACE to restart or ESC to quit', True, WHITE)
            
            text_rects = [
                game_over_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 - 40)),
                score_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2)),
                restart_text.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT//2 + 40))
            ]
            
            for text, rect in zip([game_over_text, score_text, restart_text], text_rects):
                self.screen.blit(text, rect)
        
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()


def main():
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
