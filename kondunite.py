import glob
from collections import defaultdict
from io import StringIO
from pathlib import Path

import click
import ruamel.yaml
from toposort import toposort_flatten

yaml = ruamel.yaml.YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096  # or some other big enough value to prevent line-wrap

allowed_low_level_nodes = ['replicas']


def fix_replica_templates(manifest):
    """
    Remove quotes from `replicas` value (allow templating in replicas)
    """
    fixed_manifest = []
    for s in manifest.split('\n'):
        fixed_line = s
        if 'replicas:' in s:
            key, val = s.split(':')
            fixed_line = "{}:{}".format(key, val.replace('"', '').replace("'", ''))
        fixed_manifest.append(fixed_line)

    return "\n".join(fixed_manifest)


def is_allowed_node(node_name):
    return '-' not in node_name or node_name.split('-')[0] in allowed_low_level_nodes


def yaml_contents(path):
    with open(path, 'r') as f:
        content = f.read()
        resources = content.split('---')
        for resource in resources:
            resource = resource.strip()
            resource_content = yaml.load(StringIO(resource))
            yield resource_content


def iterate_yaml_tree(node, callback):
    for name, sub_node in node.copy().items():
        callback(node, name, sub_node)
        if isinstance(sub_node, dict):
            iterate_yaml_tree(sub_node, callback)
        elif isinstance(sub_node, list):
            for item in sub_node:
                if isinstance(item, dict):
                    iterate_yaml_tree(item, callback)


def modify_targeted_nodes(node, target):
    def callback(parent, node_name, node_content):
        if not isinstance(node_content, dict) and not isinstance(node_content, list):
            if not is_allowed_node(node_name):
                # we don't support this feature on low levels nodes
                return
        if '-' in node_name:
            node_target = node_name.split('-')[-1]
            del parent[node_name]
            if node_target == target:
                parent['-'.join(node_name.split('-')[:-1])] = node_content

    iterate_yaml_tree(node, callback)


def collect_and_set_images(node, tags_by_image):
    collected_images = set()

    def callback(parent, node_name, node_content):
        if node_name == 'image':
            image_name = node_content.split(":")[0]
            if image_name in tags_by_image:
                parent[node_name] = f"{image_name}:{tags_by_image[image_name]}"
            collected_images.add(parent[node_name])

    iterate_yaml_tree(node, callback)
    return collected_images


def build_repl_images_section(collected_images, repl_registries):
    result = "\nimages:\n"
    for image in collected_images:
        image_parts = image.split(":")
        image_name = image_parts[0]
        tag = image_parts[1] if len(image_parts) > 1 else "latest"
        source = "public"
        name = image_name
        for registry in repl_registries:
            if image_name.startswith(registry):
                endpoint = registry.split("/")[0]
                source = registry.split("/")[1]
                name = image_name.split(f"{endpoint}/")[1]
                break
        result = f"{result}\n  - name: {name}\n    source: {source}\n    tag: \"{tag}\"\n"
    return result


@click.command()
@click.option('--no-recurse', is_flag=True, required=False, help="Do not recurse manifests directory", default=False)
@click.option('--target', '-t', required=True, help="Conditional target for unification", type=str)
@click.option('--img', '-i', multiple=True, required=False, help="One or more tag to specific images, provide values in the forms of 'image-name:tag', i.e gcr.io/company/server:1.0", type=str)
@click.option('--repl-base', '-b', required=False, help="Base replicated yaml definition (for '#kind: replicated' section), defaults to <directory>/replicated_base.yaml", type=str, default='')
@click.option('--output', '-o', required=False, help="File to write the unified yaml to, defaults to <target>.yaml", type=str, default='')
@click.option('--repl', '-r', is_flag=True, required=False, help="Plot output for a replicated release (with '# kind: scheduler-kubernetes' annotations)", default=False)
@click.option('--repl-registry', multiple=True, required=False, help="One or more docker registries defined in your Replicated settings in the form of endpoint:name, i.e gcr.io/company", type=str)
@click.argument('directory', type=str)
def cli(no_recurse, target, img, repl_base, output, repl, repl_registry, directory):
    manifests_contents = defaultdict(list)
    collected_images = set()
    manifests_deps = defaultdict(set)
    tags_by_image = {image.split(":")[0]: image.split(":")[1] for image in img}
    is_repl = repl
    repl_registries = repl_registry

    if not output:
        output = f"{target}.yaml"

    if not repl_base:
        repl_base = f"{directory}/replicated_base.yaml"

    recursive = not no_recurse
    manifests = glob.glob(f"{directory}/**/*.yaml" if recursive else f"{directory}/*.yaml", recursive=True)
    for manifest_file in manifests:
        if manifest_file == repl_base:
            continue
        print(f"Discovered file {manifest_file}")
        filename = Path(manifest_file).name
        manifests_deps[filename]  # just to verify there is an entry for every filename
        for manifest_content in yaml_contents(manifest_file):
            if not manifest_content:
                print(f"A manifest at {manifest_file} is an invalid yaml. Skipping.")
                continue

            if 'targetsOnly' in manifest_content:
                if manifest_content['targetsOnly'] != target:
                    continue
                del manifest_content['targetsOnly']

            if 'dependencies' in manifest_content:
                for dependent_on in manifest_content['dependencies']:
                    manifests_deps[filename].add(dependent_on)
                del manifest_content['dependencies']

            if 'replKind' in manifest_content:
                replKind = manifest_content['replKind']
                del manifest_content['replKind']
            else:
                replKind = "scheduler-kubernetes"

            modify_targeted_nodes(manifest_content, target)
            for image in collect_and_set_images(manifest_content, tags_by_image):
                collected_images.add(image)

            stream = StringIO()
            yaml.dump(manifest_content, stream)
            manifests_contents[filename].append(f"---\n# kind: {replKind}\n")
            manifests_contents[filename].append(fix_replica_templates(stream.getvalue()))

    final_collection = []
    print(manifests_deps)
    for manifest_file in toposort_flatten(manifests_deps):
        if manifest_file in manifests_contents:
            for content in manifests_contents[manifest_file]:
                final_collection.append(content.strip())

    print(f"Writing output to {output}")
    with(open(output, 'w')) as f:
        if not is_repl:
            f.write(f"\n".join(final_collection))
        else:
            with open(repl_base, 'r') as base_f:
                f.write(base_f.read())
            f.write(build_repl_images_section(collected_images, repl_registries))
            final_collection = [""] + final_collection
            f.write("\n".join(final_collection))


if __name__ == '__main__':
    pass
