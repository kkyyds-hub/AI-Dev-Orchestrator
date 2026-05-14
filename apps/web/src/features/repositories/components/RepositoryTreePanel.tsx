import type { RepositoryTreeNode } from "../../projects/types";

type RepositoryTreePanelProps = {
  nodes: RepositoryTreeNode[];
};

export function RepositoryTreePanel(props: RepositoryTreePanelProps) {
  if (props.nodes.length === 0) {
    return (
      <div className="border-l border-dashed border-[#3a3a3a] px-4 py-4 text-sm text-zinc-500">
        当前快照还没有可展示的目录摘要。
      </div>
    );
  }

  return (
    <div className="divide-y divide-[#333333] border-l border-[#333333]">
      {props.nodes.map((node) => (
        <RepositoryTreeNodeCard key={node.relative_path} node={node} depth={0} />
      ))}
    </div>
  );
}

function RepositoryTreeNodeCard(props: {
  node: RepositoryTreeNode;
  depth: number;
}) {
  const indent = Math.min(props.depth, 4) * 18;
  const isDirectory = props.node.kind === "directory";

  return (
    <div
      className="py-2 pl-4"
      style={{ paddingLeft: `${indent + 16}px` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-zinc-100">
            <span className="mr-2 text-zinc-600">{isDirectory ? "目录" : "文件"}</span>
            {props.node.name}
          </div>
          <div className="mt-1 break-all text-xs text-zinc-600">
            {props.node.relative_path}
          </div>
        </div>

        <div className="text-xs text-zinc-500">
          {isDirectory ? (
            <>
              <span>{props.node.directory_count} 个子目录</span>
              <span className="mx-2 text-zinc-700">/</span>
              <span>{props.node.file_count} 个文件</span>
            </>
          ) : (
            <span>文件</span>
          )}
        </div>
      </div>

      {props.node.truncated ? (
        <div className="mt-2 border-l border-amber-500/50 px-3 py-2 text-xs text-amber-100">
          该节点下仅保留摘要视图，未展开完整目录明细。
        </div>
      ) : null}

      {props.node.children.length > 0 ? (
        <div className="mt-2 divide-y divide-[#333333] border-l border-[#333333]">
          {props.node.children.map((child) => (
            <RepositoryTreeNodeCard
              key={child.relative_path}
              node={child}
              depth={props.depth + 1}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
