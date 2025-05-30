#!/bin/bash
# Docker构建脚本 - 提供不同的构建选项和缓存控制

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 显示帮助信息
show_help() {
    echo "Docker构建脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --no-cache     不使用Docker缓存，完全重新构建"
    echo "  --cache-only   只使用缓存构建，不重新下载"
    echo "  --deps-only    只重新安装依赖，保留应用代码缓存"
    echo "  --clean        清理所有Docker缓存后重新构建"
    echo "  --help, -h     显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                    # 快速构建（推荐）"
    echo "  $0 --deps-only       # 只重新安装Python依赖"
    echo "  $0 --no-cache        # 完全重新构建"
    echo "  $0 --clean           # 清理缓存后重新构建"
}

# 检查Docker是否可用
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        print_error "Docker未安装或不在PATH中"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker服务未运行"
        exit 1
    fi
}

# 清理Docker缓存
clean_docker_cache() {
    print_info "清理Docker构建缓存..."
    docker builder prune -f
    print_success "Docker缓存清理完成"
}

# 构建镜像
build_image() {
    local build_args="$1"
    local image_name="llm-eva"
    
    print_info "开始构建Docker镜像: $image_name"
    print_info "构建参数: $build_args"
    
    # 禁用BuildKit以避免buildx依赖问题
    export DOCKER_BUILDKIT=0
    
    if docker build $build_args -t $image_name .; then
        print_success "镜像构建成功: $image_name"
        
        # 显示镜像信息
        print_info "镜像信息:"
        docker images $image_name --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    else
        print_error "镜像构建失败"
        exit 1
    fi
}

# 主函数
main() {
    local build_mode="quick"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-cache)
                build_mode="no-cache"
                shift
                ;;
            --cache-only)
                build_mode="cache-only"
                shift
                ;;
            --deps-only)
                build_mode="deps-only"
                shift
                ;;
            --clean)
                build_mode="clean"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    print_info "Docker构建模式: $build_mode"
    
    # 检查Docker环境
    check_docker
    
    # 根据模式执行构建
    case $build_mode in
        "no-cache")
            print_warning "使用--no-cache模式，将完全重新构建"
            build_image "--no-cache"
            ;;
        "cache-only")
            print_info "使用缓存优先模式"
            build_image ""
            ;;
        "deps-only")
            print_info "重新安装依赖模式"
            # 先构建依赖阶段，强制重新安装
            print_info "步骤1: 重新构建依赖阶段..."
            build_image "--target deps-stage --no-cache"
            # 然后构建最终镜像（会使用新的依赖缓存）
            print_info "步骤2: 构建最终镜像..."
            build_image ""
            return
            ;;
        "clean")
            clean_docker_cache
            build_image "--no-cache"
            ;;
    esac
    
    print_success "构建完成！"
}

# 执行主函数
main "$@" 