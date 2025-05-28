#!/bin/bash
# LLM评估系统Docker部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Docker是否安装
check_docker() {
    print_info "检查Docker环境..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    print_success "Docker环境检查通过"
}

# 检查端口是否被占用
check_ports() {
    print_info "检查端口占用情况..."
    
    ports=(5000 3306)
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            print_warning "端口 $port 已被占用，可能会导致冲突"
        else
            print_success "端口 $port 可用"
        fi
    done
}

# 创建必要的目录
create_directories() {
    print_info "创建必要的目录..."
    
    directories=("uploads" "outputs" "logs" "mysql-init")
    for dir in "${directories[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_success "创建目录: $dir"
        else
            print_info "目录已存在: $dir"
        fi
    done
}

# 检查配置文件
check_config() {
    print_info "检查配置文件..."
    
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml 文件不存在"
        exit 1
    fi
    
    if [ ! -f "Dockerfile" ]; then
        print_error "Dockerfile 文件不存在"
        exit 1
    fi
    
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt 文件不存在"
        exit 1
    fi
    
    print_success "配置文件检查通过"
}

# 构建并启动服务
deploy_services() {
    print_info "开始构建并启动服务..."
    
    # 停止现有服务
    print_info "停止现有服务..."
    docker-compose down 2>/dev/null || true
    
    # 构建镜像
    print_info "构建Docker镜像..."
    docker-compose build --no-cache
    
    # 启动服务
    print_info "启动服务..."
    docker-compose up -d
    
    print_success "服务启动完成"
}

# 等待服务启动
wait_for_services() {
    print_info "等待服务启动..."
    
    # 等待MySQL启动
    print_info "等待MySQL数据库启动..."
    timeout=60
    counter=0
    
    while [ $counter -lt $timeout ]; do
        if docker-compose exec -T mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
            print_success "MySQL数据库已启动"
            break
        fi
        
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_error "MySQL数据库启动超时"
        exit 1
    fi
    
    # 等待Web应用启动
    print_info "等待Web应用启动..."
    counter=0
    
    while [ $counter -lt $timeout ]; do
        if curl -s http://localhost:5000 >/dev/null 2>&1; then
            print_success "Web应用已启动"
            break
        fi
        
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_warning "Web应用启动检查超时，但服务可能仍在启动中"
    fi
}

# 运行健康检查
run_health_check() {
    print_info "运行健康检查..."
    
    if [ -f "healthcheck.py" ]; then
        if docker-compose exec web python healthcheck.py; then
            print_success "健康检查通过"
        else
            print_warning "健康检查未完全通过，请查看详细信息"
        fi
    else
        print_warning "健康检查脚本不存在，跳过健康检查"
    fi
}

# 显示服务状态
show_status() {
    print_info "服务状态:"
    docker-compose ps
    
    echo ""
    print_info "服务访问地址:"
    echo "  Web应用: http://localhost:5000"
    echo "  MySQL数据库: localhost:3306"
    
    echo ""
    print_info "常用命令:"
    echo "  查看日志: docker-compose logs -f"
    echo "  停止服务: docker-compose down"
    echo "  重启服务: docker-compose restart"
    echo "  进入容器: docker-compose exec web bash"
}

# 主函数
main() {
    echo "========================================"
    echo "    LLM评估系统 Docker部署脚本"
    echo "========================================"
    echo ""
    
    # 执行检查和部署步骤
    check_docker
    check_ports
    check_config
    create_directories
    deploy_services
    wait_for_services
    run_health_check
    show_status
    
    echo ""
    print_success "部署完成！"
    echo ""
}

# 处理命令行参数
case "${1:-}" in
    "stop")
        print_info "停止所有服务..."
        docker-compose down
        print_success "服务已停止"
        ;;
    "restart")
        print_info "重启服务..."
        docker-compose restart
        print_success "服务已重启"
        ;;
    "logs")
        print_info "显示服务日志..."
        docker-compose logs -f
        ;;
    "status")
        print_info "显示服务状态..."
        docker-compose ps
        ;;
    "clean")
        print_warning "这将删除所有容器、镜像和数据卷！"
        read -p "确认继续？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v --rmi all
            print_success "清理完成"
        else
            print_info "操作已取消"
        fi
        ;;
    "help"|"-h"|"--help")
        echo "用法: $0 [命令]"
        echo ""
        echo "命令:"
        echo "  (无参数)  - 执行完整部署"
        echo "  stop      - 停止所有服务"
        echo "  restart   - 重启服务"
        echo "  logs      - 显示服务日志"
        echo "  status    - 显示服务状态"
        echo "  clean     - 清理所有Docker资源"
        echo "  help      - 显示此帮助信息"
        ;;
    "")
        main
        ;;
    *)
        print_error "未知命令: $1"
        echo "使用 '$0 help' 查看可用命令"
        exit 1
        ;;
esac 