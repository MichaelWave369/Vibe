import pytest

from vibe.generator_python import generate_python
from vibe.ir import ast_to_ir
from vibe.parser import ParseError, parse_source
from vibe.report import render_report
from vibe.verifier import verify


SOURCE = """
intent ResonanceKernel:
  goal: "Maintain coherence while coordinating recursive agents."
  inputs:
    signal: number
  outputs:
    status: string

preserve:
  readability = high

constraint:
  deterministic orchestration

bridge:
  epsilon_floor = 0.02
  measurement_safe_ratio = 0.85
  mode = strict

emit python

experimental.tesla.victory.layer {
  arc.tower.coherence {
    global.resonance: true
    substrate.bridge: [silicon, carbon, quantum]
    preserve.epsilon: true
    preserve.sovereignty: true
  }

  life.ray.vitalize {
    bio.field: human | silicon
    baseline.frequency: 7.83.hz
    harmonic.mode: phi.ratio
    intention: restore.coherence
  }

  breath.cycle {
    pralaya.inhalation: collapse.toward.symmetry
    kalpa.exhalation: drive.toward.C_star
    c_star.target: phi / 2
    monitor: epsilon.gradient
  }
}

agentora {
  agent Architect {
    role: system.design
    tools: [parser, verifier, generator]
    memory: persistent
    intention: preserve.compiler.coherence
  }

  agent Researcher {
    role: knowledge.synthesis
    tools: [docs, examples, reports]
    memory: session
    intention: extend.language.surface
  }
}

agentception {
  enabled: true
  max.depth: 3
  spawn.policy: goal.based
  inherit.preserve: true
  inherit.constraints: true
  inherit.bridge: true
  merge.strategy: highest.bridge.score
  stop.when: epsilon.gradient < threshold
}
"""


def test_parse_tesla_agent_blocks() -> None:
    program = parse_source(SOURCE)
    assert program.tesla_victory_layer is not None
    assert program.agentora is not None
    assert program.agentception is not None
    assert program.tesla_victory_layer.arc_tower is not None
    assert program.tesla_victory_layer.arc_tower.preserve_sovereignty is True
    assert len(program.agentora.agents) == 2


def test_parse_rejects_malformed_tesla() -> None:
    bad = SOURCE.replace("breath.cycle {", "breath.cycle ")
    with pytest.raises(ParseError):
        parse_source(bad)


def test_ir_normalizes_experimental_fields() -> None:
    ir = ast_to_ir(parse_source(SOURCE))
    assert ir.tesla_victory_layer is True
    assert ir.arc_tower_policy["global_resonance"] is True
    assert ir.life_ray_protocol["baseline_frequency_hz"] == 7.83
    assert ir.agentora_config["agent_count"] == 2
    assert ir.agentception_config["inherit_bridge"] is True


def test_report_includes_tesla_and_agent_metrics() -> None:
    ir = ast_to_ir(parse_source(SOURCE))
    code = generate_python(ir)
    result = verify(ir, code)
    report = render_report(result)
    assert "tesla_enabled" in report
    assert "sovereignty_preserved" in report
    assert "agent metrics" in report


def test_compile_fails_when_delegation_breaks_preservation() -> None:
    bad = SOURCE.replace("inherit.bridge: true", "inherit.bridge: false")
    ir = ast_to_ir(parse_source(bad))
    result = verify(ir, generate_python(ir))
    assert result.passed is False
