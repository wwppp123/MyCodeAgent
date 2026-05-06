"""
端到端测试：并行 vs 串行工具执行的实际耗时对比。

用法: conda run -n myenv3.12 python scripts/test_parallel_e2e.py
"""
import json, os, sys, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from concurrent.futures import ThreadPoolExecutor, as_completed


def make_simulated_tool(duration: float):
    """创建一个模拟工具，执行耗时 duration 秒。"""
    def _run(params):
        time.sleep(duration)
        return json.dumps({
            "status": "ok",
            "data": {"result": f"done after {duration}s"},
            "text": "",
            "stats": {"time_ms": int(duration * 1000)},
            "context": {"cwd": ".", "params_input": params},
        }, ensure_ascii=False)
    return _run


def run_serial(tool_calls, tools):
    """串行执行（模拟改造前的行为）。"""
    results = []
    for call in tool_calls:
        name = call["name"]
        args = call.get("arguments", {})
        observation = tools[name](args)
        results.append({"tool_name": name, "tool_call_id": call["id"], "observation": observation})
    return results


def run_parallel(tool_calls, tools):
    """并行执行（当前 _react_loop 的行为）。"""
    def execute_one(call):
        name = call["name"]
        args = call.get("arguments", {})
        observation = tools[name](args)
        return {"tool_name": name, "tool_call_id": call["id"], "observation": observation}

    if len(tool_calls) <= 1:
        return [execute_one(tool_calls[0])]

    results = [None] * len(tool_calls)
    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
        future_to_idx = {pool.submit(execute_one, call): idx for idx, call in enumerate(tool_calls)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results


def test_two_slow_tools():
    """场景1: 两个耗时工具（如读取两个大文件）"""
    tools = {
        "Read_file_a": make_simulated_tool(0.5),
        "Read_file_b": make_simulated_tool(0.5),
    }
    tool_calls = [
        {"name": "Read_file_a", "id": "c1", "arguments": {"path": "a.py"}},
        {"name": "Read_file_b", "id": "c2", "arguments": {"path": "b.py"}},
    ]

    # Serial
    start = time.time()
    serial_results = run_serial(tool_calls, tools)
    serial_time = time.time() - start

    # Parallel
    start = time.time()
    parallel_results = run_parallel(tool_calls, tools)
    parallel_time = time.time() - start

    speedup = serial_time / parallel_time if parallel_time > 0 else float("inf")
    print(f"  串行: {serial_time:.3f}s | 并行: {parallel_time:.3f}s | 加速比: {speedup:.1f}x")
    assert len(parallel_results) == 2
    assert parallel_results[0]["tool_name"] == "Read_file_a"
    assert parallel_results[1]["tool_name"] == "Read_file_b"
    return serial_time, parallel_time


def test_three_mixed_tools():
    """场景2: 三个不同耗时的工具"""
    tools = {
        "Glob": make_simulated_tool(0.2),
        "Read": make_simulated_tool(0.4),
        "Grep": make_simulated_tool(0.3),
    }
    tool_calls = [
        {"name": "Glob", "id": "c1", "arguments": {"pattern": "**/*.py"}},
        {"name": "Read", "id": "c2", "arguments": {"path": "main.py"}},
        {"name": "Grep", "id": "c3", "arguments": {"pattern": "TODO"}},
    ]

    start = time.time()
    run_serial(tool_calls, tools)
    serial_time = time.time() - start

    start = time.time()
    results = run_parallel(tool_calls, tools)
    parallel_time = time.time() - start

    speedup = serial_time / parallel_time if parallel_time > 0 else float("inf")
    print(f"  串行: {serial_time:.3f}s | 并行: {parallel_time:.3f}s | 加速比: {speedup:.1f}x")
    assert len(results) == 3
    # 保序验证
    assert results[0]["tool_name"] == "Glob"
    assert results[1]["tool_name"] == "Read"
    assert results[2]["tool_name"] == "Grep"
    return serial_time, parallel_time


def test_single_tool():
    """场景3: 单个工具（应跳过线程池）"""
    tools = {"Bash": make_simulated_tool(0.1)}
    tool_calls = [{"name": "Bash", "id": "c1", "arguments": {"command": "ls"}}]

    start = time.time()
    results = run_parallel(tool_calls, tools)
    elapsed = time.time() - start

    print(f"  耗时: {elapsed:.3f}s (单工具，无线程池开销)")
    assert len(results) == 1
    assert results[0]["tool_name"] == "Bash"
    return 0, elapsed


def test_five_parallel_tools():
    """场景4: 五个并行工具（模拟同时读取多个文件）"""
    tools = {f"Read_{i}": make_simulated_tool(0.3) for i in range(5)}
    tool_calls = [
        {"name": f"Read_{i}", "id": f"c{i}", "arguments": {"path": f"file{i}.py"}}
        for i in range(5)
    ]

    start = time.time()
    run_serial(tool_calls, tools)
    serial_time = time.time() - start

    start = time.time()
    results = run_parallel(tool_calls, tools)
    parallel_time = time.time() - start

    speedup = serial_time / parallel_time if parallel_time > 0 else float("inf")
    print(f"  串行: {serial_time:.3f}s | 并行: {parallel_time:.3f}s | 加速比: {speedup:.1f}x")
    assert len(results) == 5
    for i in range(5):
        assert results[i]["tool_name"] == f"Read_{i}"
    return serial_time, parallel_time


if __name__ == "__main__":
    print("=" * 55)
    print("并行工具执行 - 端到端耗时对比")
    print("=" * 55)

    print("\n场景1: 两个 0.5s 工具（读取两个文件）")
    s1, p1 = test_two_slow_tools()

    print("\n场景2: 三个混合耗时工具（Glob + Read + Grep）")
    s2, p2 = test_three_mixed_tools()

    print("\n场景3: 单个工具（跳过线程池）")
    test_single_tool()

    print("\n场景4: 五个并行工具（0.3s 各）")
    s4, p4 = test_five_parallel_tools()

    print("\n" + "=" * 55)
    print("汇总:")
    print(f"  场景1: {s1:.2f}s → {p1:.2f}s ({s1/p1:.1f}x)")
    print(f"  场景2: {s2:.2f}s → {p2:.2f}s ({s2/p2:.1f}x)")
    print(f"  场景4: {s4:.2f}s → {p4:.2f}s ({s4/p4:.1f}x)")
    print("=" * 55)
