import type { RepositoryTreeNode } from "../../projects/types";

type RepositoryTreePanelProps = {
  nodes: RepositoryTreeNode[];
};

export function RepositoryTreePanel(props: RepositoryTreePanelProps) {
  if (props.nodes.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 px-4 py-6 text-sm text-slate-400">
        当前快照还没有可展示的目录摘要。
      </div>
    );
  }

  return (
    <div className="space-y-3">
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
      className="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3"
      style={{ marginLeft: `${indent}px` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-100">
            {isDirectory ? "📁" : "📄"} {props.node.name}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {props.node.relative_path}
          </div>
        </div>

        <div className="text-xs text-slate-400">
          {isDirectory ? (
            <>
              <span>{props.node.directory_count} 个子目录</span>
              <span className="mx-2 text-slate-600">/</span>
              <span>{props.node.file_count} 个文件</span>
            </>
          ) : (
            <span>文件</span>
          )}
        </div>
      </div>

      {props.node.truncated ? (
        <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
          该节点下仅保留 Day02 范围内的摘要视图，未展开完整目录明细。
        </div>
      ) : null}

      {props.node.children.length > 0 ? (
        <div className="mt-3 space-y-3">
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
