# coding=utf-8
# Copyright 2022 The Fiddle-Config Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import dataclasses
import importlib
import os
import random
import sys
import types
from typing import Any
import uuid

from absl import flags
from absl.testing import absltest
from absl.testing import parameterized
import fiddle as fdl
from fiddle import daglish
from fiddle import tagging
from fiddle._src.codegen.auto_config import experimental_top_level_api
from fiddle._src.codegen.auto_config import test_fixtures
from fiddle._src.testing import nested_values
from fiddle._src.testing import test_util
from fiddle._src.testing.example import fake_encoder_decoder
from fiddle.experimental.auto_config import auto_config


@dataclasses.dataclass(frozen=True)
class ModelWrapper:
  model: Any


@dataclasses.dataclass(frozen=True)
class AnotherClass:
  foo: Any
  bar: Any


def make_arg_factory_config():
  return fdl.Partial(
      test_fixtures.EncoderLayer,
      attention=fdl.ArgFactory(
          test_fixtures.Attention,
          kernel_init=fdl.ArgFactory(
              test_fixtures.initializer, name="const", dtype="float32"
          ),
      ),
  )


class ExperimentalTopLevelApiTest(test_util.TestCase, parameterized.TestCase):

  def get_tempdir(self):
    try:
      flags.FLAGS.test_tmpdir
    except flags.UnparsedFlagAccessError:
      # Sometimes need to initialize flags when running `pytest`.
      program, *rest = sys.argv
      rest = [flag for flag in rest if "test_tmpdir" in flag]
      flags.FLAGS([program, *rest])
    return self.create_tempdir().full_path

  def _load_code_as_module(self, code: str) -> types.ModuleType:
    # Write the generated config to a module, and load it. We can't just exec()
    # it because auto_config needs access to the source code.
    temp_dir = self.get_tempdir()
    sys.path.append(temp_dir)
    uuid_str = str(hash(uuid.uuid4()))
    file_path = os.path.join(temp_dir, f"config_{uuid_str}.py")
    with open(file_path, "w") as f:
      f.write(code)
    return importlib.import_module(f"config_{uuid_str}")

  @parameterized.named_parameters([
      {
          "testcase_name": "shared_config",
          "config": test_fixtures.unprocessed_shared_config().original_config,
      },
      {
          "testcase_name": "arg_factory_config",
          "config": make_arg_factory_config(),
      },
      {
          "testcase_name": "encoder_decoder_config",
          "config": fake_encoder_decoder.fixture.as_buildable(),
      },
  ])
  def test_generates_equivalent_configs(self, config):
    code = experimental_top_level_api.auto_config_codegen(config)
    module = self._load_code_as_module(code)
    generated_config = module.config_fixture.as_buildable()
    self.assertDagEqual(config, generated_config)

  def test_fuzz(self):
    # TODO(b/272826193): Test on more RNG seeds.
    for i in range(10):
      config = tagging.materialize_tags(
          nested_values.generate_nested_value(random.Random(i))
      )
      # `auto_config` checks that a Buildable is returned, to avoid user errors.
      has_buildables = any(
          isinstance(value, fdl.Buildable)
          for value, _ in daglish.iterate(config)
      )
      if has_buildables:
        with self.subTest(f"rng_{i}"):
          code = experimental_top_level_api.auto_config_codegen(config)
          module = self._load_code_as_module(code)
          generated_config = module.config_fixture.as_buildable()
          self.assertDagEqual(config, generated_config)

  def test_config_contains_tags_wo_default(self):
    @dataclasses.dataclass
    class Foo:
      a: int = 1

    config = fdl.Config(Foo)
    fdl.set_tags(config, "a", [test_fixtures.ATag])

    with self.assertRaisesRegex(
        ValueError,
        (
            "assigning a value to the field first or removing field tags from "
            "your config"
        ),
    ):
      experimental_top_level_api.auto_config_codegen(config)

  def test_sub_fixtures_with_shared_nodes(self):
    config = fake_encoder_decoder.fixture.as_buildable()
    for complexity in [None, 2, 3]:
      with self.subTest(f"max_complexity_as_{complexity}"):
        code = experimental_top_level_api.auto_config_codegen(
            config,
            sub_fixtures={
                "fake_encoder": config.encoder,
                "fake_decoder": config.decoder,
            },
            max_expression_complexity=complexity,
        )
        module = self._load_code_as_module(code)
        generated_config = module.config_fixture.as_buildable()
        self.assertDagEqual(config, generated_config)

  def test_nested_sub_fixture(self):
    config = fake_encoder_decoder.fixture.as_buildable()
    code = experimental_top_level_api.auto_config_codegen(
        config,
        sub_fixtures={
            "fake_encoder": config.encoder,
            "attention": config.encoder.attention,
        },
    )
    module = self._load_code_as_module(code)
    generated_config = module.config_fixture.as_buildable()
    self.assertDagEqual(config, generated_config)

  def test_sub_fixtures_interaction_w_move_shared_nodes_to_variables(self):
    config = fake_encoder_decoder.fixture.as_buildable()
    code = experimental_top_level_api.auto_config_codegen(
        config, sub_fixtures={"embedder": config.encoder.embedders["tokens"]}
    )
    module = self._load_code_as_module(code)
    generated_config = module.config_fixture.as_buildable()
    self.assertDagEqual(config, generated_config)

  def test_sub_fixtures_interaction_w_move_complex_nodes_to_variables(self):
    config = fake_encoder_decoder.fixture.as_buildable()
    # Let the sub-fixture has two shared nodes so that the interaction between
    # move_complex_nodes_to_variables pass and sub-fixture args can be tested.
    config.decoder.self_attention = config.encoder.attention
    for complexity in [None, 2, 3]:
      with self.subTest(f"max_complexity_as_{complexity}"):
        code = experimental_top_level_api.auto_config_codegen(
            config,
            sub_fixtures={"fake_encoder": config.encoder},
            max_expression_complexity=complexity,
        )
        module = self._load_code_as_module(code)
        generated_config = module.config_fixture.as_buildable()
        self.assertDagEqual(config, generated_config)

  def test_sub_fixture_is_shared(self):
    config = fake_encoder_decoder.fixture.as_buildable()
    for complexity in [None, 2, 3]:
      with self.subTest(f"max_complexity_as_{complexity}"):
        code = experimental_top_level_api.auto_config_codegen(
            config,
            sub_fixtures={"embedder": config.encoder.embedders["tokens"]},
            max_expression_complexity=complexity,
        )
        module = self._load_code_as_module(code)
        generated_config = module.config_fixture.as_buildable()
        self.assertDagEqual(config, generated_config)

  def test_sub_fixture_has_sharing_nodes(self):
    @auto_config
    def fixture():
      return fake_encoder_decoder.ModelWrapper(
          model=fake_encoder_decoder.fixture()
      )

    config = fixture.as_buildable()
    for complexity in [None, 2, 3]:
      with self.subTest(f"max_complexity_as_{complexity}"):
        code = experimental_top_level_api.auto_config_codegen(
            config,
            sub_fixtures={"model_fixture": config.model},
            max_expression_complexity=complexity,
        )
        module = self._load_code_as_module(code)
        generated_config = module.config_fixture.as_buildable()
        self.assertDagEqual(config, generated_config)


if __name__ == "__main__":
  absltest.main()
