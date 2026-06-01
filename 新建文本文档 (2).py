# 在你的主程序环境中运行这个检查
def quick_diagnosis():
    print("="*50)
    print("ZPP011 审核表格数据检查")
    print("="*50)
    
    # 检查关键变量
    print(f"1. audit_data 是否存在: {hasattr(self, 'audit_data')}")
    if hasattr(self, 'audit_data'):
        print(f"   audit_data 类型: {type(self.audit_data)}")
        if self.audit_data is not None:
            print(f"   数据行数: {len(self.audit_data)}")
            print(f"   列名: {list(self.audit_data.columns) if hasattr(self.audit_data, 'columns') else 'N/A'}")
        else:
            print("   audit_data 为 None")
    else:
        print("   audit_data 不存在")
    
    print(f"\n2. audit_tree 是否存在: {hasattr(self, 'audit_tree')}")
    if hasattr(self, 'audit_tree'):
        print(f"   表格列: {self.audit_tree['columns'] if hasattr(self.audit_tree, 'columns') else 'N/A'}")
        children = self.audit_tree.get_children() if hasattr(self.audit_tree, 'get_children') else []
        print(f"   当前项目数: {len(children)}")
    else:
        print("   audit_tree 不存在")
    
    print(f"\n3. 输入文件: {self.input_file.get() if hasattr(self, 'input_file') else 'N/A'}")
    print(f"4. 输出路径: {self.output_path if hasattr(self, 'output_path') else 'N/A'}")
    
    # 检查关键列
    if hasattr(self, 'audit_data') and self.audit_data is not None:
        required_cols = ['偏差率(%)', '物料编码', '物料名称', 'excel_row']
        missing_cols = [col for col in required_cols if col not in self.audit_data.columns]
        if missing_cols:
            print(f"\n⚠️  缺失关键列: {missing_cols}")
        else:
            print(f"\n✅ 所有关键列都存在")
    
    print("="*50)

# 运行检查
quick_diagnosis()


