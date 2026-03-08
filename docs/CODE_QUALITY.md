# 代码质量保证指南

## 1. 移除无用的导入

### 1.1 使用 Ruff 检测无用导入

Ruff 是一个快速的 Python 代码检查工具，可以检测和自动修复无用的导入。

**检测命令**：
```bash
uv run ruff check --select F401 src/
```

**自动修复命令**：
```bash
uv run ruff check --select F401 --fix src/
```

### 1.2 配置 Ruff

在 `pyproject.toml` 文件中添加以下配置：

```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
fixable = ["E", "F", "W", "I"]
```

这样，当你运行 `ruff check --fix` 时，Ruff 会自动修复包括无用导入在内的问题。

## 2. 代码格式化

### 2.1 使用 Ruff 进行代码格式化

**检查代码格式**：
```bash
uv run ruff check src/
```

**自动修复代码格式**：
```bash
uv run ruff check src/ --fix
```

### 2.2 集成到开发流程

**在 VS Code 中**：
1. 安装 Ruff 扩展
2. 在设置中启用自动修复：
   ```json
   {
     "editor.codeActionsOnSave": {
       "source.fixAll": true
     }
   }
   ```

**在 pre-commit 钩子中**：
在 `.pre-commit-config.yaml` 文件中添加 Ruff 钩子：
```yaml
repos:
-   repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
    -   id: ruff
        args: ["--fix"]
```

## 3. 其他工具

除了 Ruff，你还可以使用：

- **autoflake**：专门用于移除未使用的导入和变量
  ```bash
  autoflake --remove-all-unused-imports --in-place --recursive src/
  ```

- **pyflakes**：检测未使用的导入
  ```bash
  pyflakes src/
  ```

## 4. 最佳实践

1. **定期运行检查**：在 CI/CD 流程中集成 Ruff 检查
2. **使用编辑器集成**：在保存文件时自动修复
3. **团队约定**：建立代码质量标准，确保所有开发者都使用相同的工具和配置

通过这些方法，你可以确保代码中不会存在无用的导入，保持代码的整洁和高效。
