"""Board TOON parser tests."""

import json

from pymagnific.parsers.board_toon import (
    creations_from_board,
    parse_board_json,
    parse_creations,
    subset_board,
    summarize_space,
)
from pymagnific.services.assets_service import AssetsService

SAMPLE_STATE = """
board:
  uuid: test-space-uuid
  elementsCount: 2
  connectionsCount: 1
nodes[3]{id,type,name,selected,x,y,width,height,pageId,sourceNodeId,groupId,panelIndex,workflowStatus}:
  panel-1,panel,Input,false,0,0,100,100,"1",null,null,null,null
  node-a,creation,Product,false,0,0,100,100,"1",null,panel-1,null,null
  node-b,creation,Material reference,false,0,0,100,100,"1",null,panel-1,null,null
nodeData[2]{elementId,key,value}:
  node-a,creationIdentifier,ABC123
  node-b,creationIdentifier,DEF456
connections[1]{id,sourceElementId,sourcePort,targetElementId,targetPort,dataType,pageId,sourcePageId,targetPageId,selected}:
  conn-1,node-a,out,gen-1,in,image,"1","1","1",false
"""


def test_parse_board_json():
    board = parse_board_json(SAMPLE_STATE)
    assert board["board"]["uuid"] == "test-space-uuid"
    assert len(board["nodes"]) == 3
    assert len(board["connections"]) == 1
    assert board["connections"][0]["sourceElementId"] == "node-a"


def test_parse_creations():
    creations = parse_creations(SAMPLE_STATE)
    assert len(creations) == 2
    by_name = {c.name: c.creation_identifier for c in creations}
    assert by_name["Product"] == "ABC123"
    assert by_name["Material reference"] == "DEF456"


def test_summarize_space():
    summary = summarize_space(SAMPLE_STATE)
    assert summary["spaceId"] == "test-space-uuid"
    assert summary["creationCount"] == 2
    assert summary["connectionCount"] == 1
    assert len(summary["panels"]) == 1


def test_subset_by_panel(tmp_path):
    export = tmp_path / "export"
    export.mkdir()
    board = parse_board_json(SAMPLE_STATE)
    (export / "board.json").write_text(json.dumps(board), encoding="utf-8")

    service = AssetsService()
    subset = service.subset_export(export, panel=["Input"])
    ids = {n["id"] for n in subset["nodes"]}
    assert ids == {"panel-1", "node-a", "node-b"}
    assert len(subset["connections"]) == 0


def test_subset_by_type():
    board = parse_board_json(SAMPLE_STATE)
    subset = subset_board(board, node_type=["creation"])
    assert len(subset["nodes"]) == 2
    assert all(n["type"] == "creation" for n in subset["nodes"])


def test_creations_from_board():
    board = parse_board_json(SAMPLE_STATE)
    creations = creations_from_board(board)
    assert len(creations) == 2
